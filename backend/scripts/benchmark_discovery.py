"""Authentic mixed-category retrieval and optional actual Jev pair evaluation.

No scripted answers enter quality metrics. This small corpus is not representative
of exchange-wide recall, calibrated model accuracy, or settlement qualification.
"""

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

import httpx

from arbbot.config import Settings
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.matching.classification_input import VERSION, build_request
from arbbot.matching.classification_provider import DecisionsProvider, ProviderFailure
from arbbot.matching.extraction import extract_contract
from arbbot.matching.retrieval import Encoder, description, semantic_pairs
from arbbot.matching.service import match_markets, retrieve_candidates
from arbbot.storage.database import Database
from arbbot.storage.models import Base
from arbbot.storage.repository import Repository

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/discovery_broad"


def load():
    records = json.loads((FIXTURES / "recorded.json").read_text(), parse_float=str)["markets"]
    markets = []
    for row in records:
        adapter = KalshiAdapter if row["venue"] == "kalshi" else PolymarketUSAdapter
        market = adapter.normalize_market(row["payload"])
        if "category" in row:
            market = market.model_copy(update={"category": row["category"]})
        markets.append(market)
    return markets, json.loads((FIXTURES / "labels.json").read_text())["pairs"]


async def run(args):
    markets, labels = load()
    settings = Settings()
    start = time.perf_counter()
    lexical, _ = retrieve_candidates(markets, {}, [], limit=10)
    keyword_keys = {tuple(sorted((a.id, b.id))) for a, b in lexical}
    encoded = await asyncio.to_thread(Encoder(settings).encode, [description(m) for m in markets])
    semantic = await asyncio.to_thread(
        semantic_pairs, markets, dict(zip((m.id for m in markets), encoded, strict=True)), 10
    )
    definitions = [extract_contract(m).definition for m in markets]
    legacy = {
        tuple(sorted((m.left_id, m.right_id))) for m in match_markets(markets, [], definitions)
    }
    positives = [r for r in labels if r["event_label"] == "same_event"]

    def recalled(keys):
        return sum(tuple(sorted((r["left_id"], r["right_id"]))) in keys for r in positives)

    result = {
        "question_set_version": VERSION,
        "contracts": len(markets),
        "categories": sorted({m.category_group for m in markets}),
        "labeled_pairs": len(labels),
        "event_positive_labels": len(positives),
        "legacy_title_admission_recall_count": recalled(legacy),
        "keyword_top10_bidirectional_recall_count": recalled(keyword_keys),
        "hybrid_top10_bidirectional_recall_count": recalled(keyword_keys | semantic),
        "retrieval_seconds_including_model_load": time.perf_counter() - start,
        "model_results": [],
        "limitations": [
            "Small source-reading corpus; not representative accuracy or exhaustive recall.",
            "Event labels and outcome orientation are separate from settlement compatibility.",
            "CPI and weather supply unrelated cases; no US economic counterpart is invented.",
            "Legacy metric replays title/definition admission, not the old deployed worker.",
            "Document applicability and exceptional settlement coverage remain incomplete.",
        ],
    }
    if args.live:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the explicit live benchmark")
        with tempfile.TemporaryDirectory(prefix="arbbot-discovery-benchmark-") as directory:
            db = Database(
                Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{directory}/db")
            )
            try:
                async with db.engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                repository = Repository(db)
                for market in markets:
                    await repository.save_market(market)
                async with httpx.AsyncClient() as client:
                    provider = DecisionsProvider(
                        client, settings.openrouter_api_key.get_secret_value()
                    )
                    for label in labels:
                        async with db.sessions() as session:
                            built = await build_request(
                                session,
                                "live",
                                (label["left_id"], label["right_id"]),
                                settings.classification_model,
                            )
                        started = time.perf_counter()
                        try:
                            answer, attempts = await provider.decide(built[1])
                            result["model_results"].append(
                                {
                                    **label,
                                    "returned_model": answer.model,
                                    "answers": {
                                        k: v.model_dump() for k, v in answer.answers.items()
                                    },
                                    "usage": answer.usage,
                                    "attempts": attempts,
                                    "seconds": time.perf_counter() - started,
                                }
                            )
                        except ProviderFailure as exc:
                            result["model_results"].append({**label, "error": exc.code})
            finally:
                await db.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "model_results"}, indent=2))
    if args.live:
        answered = [r for r in result["model_results"] if "answers" in r]
        print(
            json.dumps(
                {
                    "answered": len(answered),
                    "errors": len(labels) - len(answered),
                    "event_label_agreement": sum(
                        r["answers"]["event"]["choice"] == r["event_label"] for r in answered
                    ),
                    "orientation_label_agreement": sum(
                        r["answers"]["orientation"]["choice"] == r["outcome_relation"]
                        for r in answered
                    ),
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    asyncio.run(run(parser.parse_args()))
