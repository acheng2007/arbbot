"""Pinned CPU embeddings. Retrieval proposes pairs; it never proves equivalence."""

import asyncio
import math
from pathlib import Path

from sqlalchemy import select

from arbbot.domain import digest, utcnow
from arbbot.storage.models import EmbeddingRecord, RetrievalStateRecord

MODEL = "BAAI/bge-small-en-v1.5"
REPOSITORY = "Qdrant/bge-small-en-v1.5-onnx-Q"
REVISION = "aa8f8b060edb00e03bfdd08813a2949946c8ba55"
VERSION = f"{MODEL}/{REVISION}/description-v1"


def description(market):
    # Prices, capture times and source receipts must not cause re-embedding.
    return f"{market.title}\n{market.rules[:1800]}"


def content_hash(market):
    return digest([VERSION, description(market)])


class Encoder:
    def __init__(self, settings):
        self.settings, self.model = settings, None

    def encode(self, texts):
        if self.model is None:
            from fastembed import TextEmbedding
            from huggingface_hub import snapshot_download

            path = snapshot_download(
                REPOSITORY,
                revision=REVISION,
                cache_dir=str(self.settings.embedding_cache),
                allow_patterns=["*.json", "*.txt", "*.onnx"],
                local_files_only=self.settings.embedding_local_only,
            )
            self.model = TextEmbedding(
                MODEL, specific_model_path=path, threads=2, local_files_only=True
            )
        vectors = [v.tolist() for v in self.model.embed(texts, batch_size=32)]
        for vector in vectors:
            if len(vector) != 384 or not all(math.isfinite(v) for v in vector):
                raise ValueError("Invalid embedding")
        return vectors


def semantic_pairs(markets, vectors, limit=50):
    """Bidirectional exact search over the current indexed catalog, in blocks."""
    import numpy as np

    rows = [m for m in sorted(markets, key=lambda m: m.id) if m.id in vectors]
    if not rows:
        return set()
    matrix = np.asarray([vectors[m.id] for m in rows], dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.maximum(norms, 1e-12)
    pairs = set()
    for start in range(0, len(rows), 64):
        scores = matrix[start : start + 64] @ matrix.T
        for index, values in enumerate(scores):
            market = rows[start + index]
            # ID is a deterministic tie-breaker, not a similarity cutoff.
            eligible = [
                i
                for i, other in enumerate(rows)
                if other.mode == market.mode and other.venue != market.venue
            ]
            eligible.sort(key=lambda i: (-float(values[i]), rows[i].id))
            for i in eligible[:limit]:
                pairs.add(tuple(sorted((market.id, rows[i].id))))
    return pairs


class HybridRetriever:
    def __init__(self, settings, database, changed=None, encoder=None):
        self.settings, self.database = settings, database
        self.changed = changed or asyncio.Event()
        self.encoder = encoder or Encoder(settings)
        self.pairs = set()
        self.vectors = {}
        self.fingerprints = {}
        self.retry_at = 0.0

    async def refresh(self, markets):
        enabled = (
            self.settings.semantic_retrieval
            and self.settings.mode == "live"
            and not self.settings.recording_file
        )
        now = utcnow()
        state = {
            "state": "disabled",
            "model": MODEL,
            "revision": REVISION,
            "catalog": len(markets),
            "indexed": 0,
            "error": None,
        }
        if enabled:
            indexed = {m.id: m for m in markets}
            hashes = {m.id: content_hash(m) for m in markets}
            async with self.database.sessions() as session:
                records = (
                    await session.scalars(
                        select(EmbeddingRecord).where(
                            EmbeddingRecord.model_version == VERSION,
                            EmbeddingRecord.input_hash.in_(hashes.values()),
                            EmbeddingRecord.market_key.in_([f"{m.mode}:{m.id}" for m in markets]),
                        )
                    )
                ).all()
                previous = await session.get(RetrievalStateRecord, self.settings.mode)
                cursor = (previous.payload if previous else {}).get("cursor", "")
            vectors = {}
            for row in records:
                mid = row.market_key.removeprefix(self.settings.mode + ":")
                if hashes.get(mid) == row.input_hash:
                    vectors[mid] = row.vector
            pending = sorted(mid for mid in indexed if mid not in vectors)
            ordered = [mid for mid in pending if mid > cursor] + [
                mid for mid in pending if mid <= cursor
            ]
            state.update(state="pending" if pending else "healthy", cursor=cursor)
            if pending and asyncio.get_running_loop().time() >= self.retry_at:
                batch = ordered[:64]
                try:
                    encoded = await asyncio.to_thread(
                        self.encoder.encode, [description(indexed[mid]) for mid in batch]
                    )
                    if len(encoded) != len(batch):
                        raise ValueError("Incomplete embedding batch")
                    async with self.database.sessions.begin() as session:
                        for mid, vector in zip(batch, encoded, strict=True):
                            market = indexed[mid]
                            await session.merge(
                                EmbeddingRecord(
                                    key=digest([market.mode, mid, hashes[mid]]),
                                    market_key=f"{market.mode}:{mid}",
                                    input_hash=hashes[mid],
                                    model_version=VERSION,
                                    vector=vector,
                                    created_at=now,
                                )
                            )
                            vectors[mid] = vector
                    state.update(
                        cursor=batch[-1],
                        state="healthy" if len(vectors) == len(markets) else "pending",
                    )
                except Exception:
                    # Sanitize network/model errors; lexical search never stops.
                    self.retry_at = asyncio.get_running_loop().time() + 60
                    state.update(state="degraded", error="embedding_unavailable", cursor=batch[-1])
            elif pending and self.retry_at:
                state.update(state="degraded", error="embedding_unavailable")
            pairs = await asyncio.to_thread(semantic_pairs, markets, vectors)
            changed = pairs != self.pairs or hashes != self.fingerprints
            self.pairs, self.vectors, self.fingerprints = pairs, vectors, hashes
            state["indexed"] = len(vectors)
            if changed:
                self.changed.set()
        async with self.database.sessions.begin() as session:
            await session.merge(
                RetrievalStateRecord(
                    mode=self.settings.mode,
                    payload=state,
                    updated_at=now,
                )
            )

    def current_pairs(self, markets):
        indexed = {m.id: m for m in markets}
        valid = {mid for mid, m in indexed.items() if self.fingerprints.get(mid) == content_hash(m)}
        return {p for p in self.pairs if all(mid in valid for mid in p)}

    def candidates(self, markets):
        from arbbot.matching.service import retrieve_candidates

        lexical, _ = retrieve_candidates(markets, {}, [])
        methods = {tuple(sorted((a.id, b.id))): ("keyword",) for a, b in lexical}
        for pair in self.current_pairs(markets):
            methods[pair] = (*methods.get(pair, ()), "semantic")
        return methods


if __name__ == "__main__":
    # Explicit image/model provisioning; no exchange or paid-provider requests.
    from arbbot.config import Settings

    encoder = Encoder(Settings(_env_file=None))
    encoder.encode(["Provision the pinned local retrieval model."])
    print(f"Provisioned {MODEL} at {Path(encoder.settings.embedding_cache)}")
