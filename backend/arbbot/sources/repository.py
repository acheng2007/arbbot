"""Durable storage for settlement source evidence."""

from collections import defaultdict

from sqlalchemy import or_, select, text, update
from sqlalchemy.exc import IntegrityError

from arbbot.domain import Mode
from arbbot.sources.models import (
    MAX_CONTENT_BYTES,
    SourceArtifact,
    SourceArtifactSummary,
    SourceCapture,
    SourceFailure,
)
from arbbot.sources.versions import latest_document, lock_document
from arbbot.storage.models import MarketRecord, OpportunityRecord, SourceArtifactRecord
from arbbot.storage.repository import aware


def market_key(mode: Mode, market_id: str) -> str:
    return f"{mode}:{market_id}"


def artifact(row: SourceArtifactRecord) -> SourceArtifact:
    mode, _, market_id = row.market_key.partition(":")
    return SourceArtifact(
        id=row.id,
        venue=row.venue,
        mode=mode,
        market_id=market_id,
        url=row.url,
        label=row.label,
        status=row.status,
        content=row.content,
        content_type=row.content_type,
        content_digest=row.content_digest,
        byte_size=row.byte_size,
        source_at=aware(row.source_at) if row.source_at else None,
        reason=row.reason,
        detail=row.detail,
        status_code=row.status_code,
        market_terms_hash=row.market_terms_hash,
        first_seen_at=aware(row.first_seen_at),
        last_seen_at=aware(row.last_seen_at),
        observations=row.observations,
        details=row.details,
    )


class SourceRepository:
    def __init__(self, database, max_content_bytes: int = MAX_CONTENT_BYTES):
        if not 0 < max_content_bytes <= MAX_CONTENT_BYTES:
            raise ValueError(f"Document limit must be between 1 and {MAX_CONTENT_BYTES} bytes")
        self.database = database
        self.max_content_bytes = max_content_bytes

    async def get(self, mode: Mode, artifact_id: str) -> SourceArtifact | None:
        async with self.database.sessions() as session:
            row = await session.scalar(
                select(SourceArtifactRecord)
                .join(MarketRecord, MarketRecord.key == SourceArtifactRecord.market_key)
                .where(SourceArtifactRecord.id == artifact_id, MarketRecord.mode == mode)
            )
            return artifact(row) if row else None

    async def summaries(self, mode: Mode, market_id: str, *, limit=20, offset=0):
        # Avoid materializing binary documents just to list provenance.
        columns = [
            column for column in SourceArtifactRecord.__table__.columns if column.name != "content"
        ]
        query = (
            select(*columns)
            .where(SourceArtifactRecord.market_key == market_key(mode, market_id))
            .order_by(SourceArtifactRecord.last_seen_at.desc(), SourceArtifactRecord.id)
            .limit(limit)
            .offset(offset)
        )
        async with self.database.sessions() as session:
            rows = (await session.execute(query)).mappings().all()
            return [
                SourceArtifactSummary.model_validate(
                    {
                        **{k: v for k, v in row.items() if k != "market_key"},
                        "mode": mode,
                        "market_id": market_id,
                        "first_seen_at": aware(row["first_seen_at"]),
                        "last_seen_at": aware(row["last_seen_at"]),
                        "source_at": aware(row["source_at"]) if row["source_at"] else None,
                    }
                )
                for row in rows
            ]

    async def record(self, event: SourceCapture | SourceFailure) -> SourceArtifact:
        """Persist one retrieval attempt.

        Repeating an identical capture or an identical failure records another
        observation of the same immutable artifact rather than a new one.
        """
        if isinstance(event, SourceCapture) and len(event.content) > self.max_content_bytes:
            raise ValueError(
                f"Document of {len(event.content)} bytes exceeds the "
                f"{self.max_content_bytes} byte limit; record a too_large failure instead"
            )
        try:
            return await self._record(event)
        except IntegrityError:
            # A concurrent writer inserted the same artifact first.
            return await self._record(event)

    async def _record(self, event: SourceCapture | SourceFailure) -> SourceArtifact:
        key = market_key(event.mode, event.market_id)
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            market = await session.get(MarketRecord, key, with_for_update=True)
            if market is None:
                raise ValueError("Market must be persisted before its settlement sources")
            if market.venue != event.venue:
                raise ValueError("Source evidence must name the venue that lists the market")
            await lock_document(session, event.mode, event.url)
            previous = await latest_document(session, event.mode, event.url)
            newer = not previous or (event.observed_at, event.id) > (
                aware(previous.last_seen_at),
                previous.id,
            )
            generation = previous.details.get("source_generation", 0) if previous else 0
            last_digest = (
                previous.details.get("last_capture_digest", previous.content_digest)
                if previous
                else None
            )
            content_changed = (
                isinstance(event, SourceCapture) and last_digest and event.digest != last_digest
            )
            if newer and content_changed:
                generation += 1
                market.payload = {
                    **market.payload,
                    "source_revision": market.payload.get("source_revision", 0) + 1,
                }
            if (
                newer
                and previous
                and (
                    previous.status
                    != ("captured" if isinstance(event, SourceCapture) else "failed")
                    or content_changed
                )
            ):
                # A shared rulebook or product specification can support several markets.
                dependent_ids = (
                    select(MarketRecord.id)
                    .join(SourceArtifactRecord, SourceArtifactRecord.market_key == MarketRecord.key)
                    .where(MarketRecord.mode == event.mode, SourceArtifactRecord.url == event.url)
                )
                await session.execute(
                    update(OpportunityRecord)
                    .where(
                        OpportunityRecord.mode == event.mode,
                        or_(
                            *(
                                OpportunityRecord.payload["legs"][i]["market_id"]
                                .as_string()
                                .in_(dependent_ids)
                                for i in (0, 1)
                            )
                        ),
                    )
                    .values(active=False)
                )
            row = await session.get(SourceArtifactRecord, event.id, with_for_update=True)
            if row is None:
                row = self._new_row(event, key, market.payload["terms_hash"])
                session.add(row)
            else:
                self._observe(row, event)
            if newer:
                row.details = {
                    **row.details,
                    "source_generation": generation,
                    "last_capture_digest": event.digest
                    if isinstance(event, SourceCapture)
                    else last_digest,
                }
            await session.flush()
            return artifact(row)

    @staticmethod
    def _new_row(
        event: SourceCapture | SourceFailure, key: str, terms_hash: str
    ) -> SourceArtifactRecord:
        captured = isinstance(event, SourceCapture)
        return SourceArtifactRecord(
            id=event.id,
            market_key=key,
            venue=event.venue,
            url=event.url,
            label=event.label,
            status="captured" if captured else "failed",
            content=event.content if captured else None,
            content_type=event.content_type if captured else None,
            content_digest=event.digest if captured else None,
            byte_size=len(event.content) if captured else 0,
            source_at=event.source_at if captured else None,
            reason=None if captured else event.reason,
            detail=None if captured else event.detail,
            status_code=None if captured else event.status_code,
            market_terms_hash=terms_hash,
            first_seen_at=event.observed_at,
            last_seen_at=event.observed_at,
            observations=1,
            details=event.details,
        )

    @staticmethod
    def _observe(row: SourceArtifactRecord, event: SourceCapture | SourceFailure) -> None:
        if isinstance(event, SourceCapture) and row.content_digest != event.digest:
            raise ValueError("Stored source artifacts are immutable")
        row.observations += 1
        row.last_seen_at = max(aware(row.last_seen_at), event.observed_at)
        row.first_seen_at = min(aware(row.first_seen_at), event.observed_at)

    async def artifacts(
        self,
        mode: Mode,
        market_id: str,
        *,
        label: str | None = None,
        url: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SourceArtifact]:
        """Return observed artifacts for a market, most recently observed first."""
        query = select(SourceArtifactRecord).where(
            SourceArtifactRecord.market_key == market_key(mode, market_id)
        )
        if label:
            query = query.where(SourceArtifactRecord.label == label)
        if url:
            query = query.where(SourceArtifactRecord.url == url)
        query = (
            query.order_by(SourceArtifactRecord.last_seen_at.desc(), SourceArtifactRecord.id)
            .limit(limit)
            .offset(offset)
        )
        async with self.database.sessions() as session:
            return [artifact(row) for row in (await session.scalars(query)).all()]

    async def latest(
        self, mode: Mode, market_id: str, url: str, label: str
    ) -> SourceArtifact | None:
        """Return the most recent observation for one document."""
        found = await self.artifacts(mode, market_id, label=label, url=url, limit=1)
        return found[0] if found else None

    async def missing_evidence(
        self, mode: Mode, market_id: str, labels: list[str], *, terms_hash: str | None = None
    ) -> list[str]:
        """Return requested labels that are not backed by current usable evidence.

        A label is missing when nothing was captured for it, when the most
        recent observation of any of its documents failed, or when its evidence
        predates the supplied market terms.
        """
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(SourceArtifactRecord).where(
                        SourceArtifactRecord.market_key == market_key(mode, market_id),
                        SourceArtifactRecord.label.in_(labels),
                    )
                )
            ).all()
        current: dict[tuple[str, str], SourceArtifactRecord] = {}
        for row in rows:
            key = (row.label, row.url)
            previous = current.get(key)
            if previous is None or self._observed_after(row, previous):
                current[key] = row
        usable: dict[str, list[bool]] = defaultdict(list)
        for (label, _), row in current.items():
            stale_terms = terms_hash is not None and row.market_terms_hash != terms_hash
            usable[label].append(row.status == "captured" and not stale_terms)
        return [label for label in labels if not usable[label] or not all(usable[label])]

    @staticmethod
    def _observed_after(row: SourceArtifactRecord, other: SourceArtifactRecord) -> bool:
        return (aware(row.last_seen_at), row.id) > (aware(other.last_seen_at), other.id)
