from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from arbbot.sources.models import SourceCapture
from arbbot.storage.models import MarketRecord, SourceArtifactRecord, SourceCaptureRecord
from arbbot.storage.repository import aware


class SourceRepository:
    def __init__(self, database):
        self.database = database

    async def capture(self, capture: SourceCapture) -> str:
        """Insert immutable evidence and attempts atomically, including concurrent retries."""
        insert = (
            postgres_insert if self.database.engine.dialect.name == "postgresql" else sqlite_insert
        )
        market_key = f"{capture.mode}:{capture.market_id}"
        async with self.database.sessions.begin() as session:
            market = await session.get(MarketRecord, market_key)
            if market is None or market.venue != capture.venue:
                raise ValueError(
                    "Evidence requires a persisted market from the same venue and mode"
                )
            if capture.artifact_id:
                await session.execute(
                    insert(SourceArtifactRecord)
                    .values(
                        id=capture.artifact_id,
                        market_key=market_key,
                        venue=capture.venue,
                        url=str(capture.url),
                        content_type=capture.content_type,
                        content_digest=capture.content_digest,
                        content=capture.content,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )
            await session.execute(
                insert(SourceCaptureRecord)
                .values(
                    id=capture.capture_id,
                    market_key=market_key,
                    artifact_id=capture.artifact_id,
                    venue=capture.venue,
                    url=str(capture.url),
                    retrieved_at=capture.retrieved_at,
                    content_type=capture.content_type,
                    failure=capture.failure,
                    http_status=capture.http_status,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        return capture.capture_id

    async def history(self, mode, market_id, *, limit=100, offset=0) -> list[SourceCapture]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("History requires limit 1..100 and nonnegative offset")
        async with self.database.sessions() as session:
            rows = await session.execute(
                select(SourceCaptureRecord, SourceArtifactRecord)
                .outerjoin(
                    SourceArtifactRecord, SourceCaptureRecord.artifact_id == SourceArtifactRecord.id
                )
                .where(SourceCaptureRecord.market_key == f"{mode}:{market_id}")
                .order_by(SourceCaptureRecord.retrieved_at.desc(), SourceCaptureRecord.id)
                .limit(limit)
                .offset(offset)
            )
            return [
                SourceCapture(
                    mode=mode,
                    market_id=market_id,
                    venue=capture.venue,
                    url=capture.url,
                    retrieved_at=aware(capture.retrieved_at),
                    content_type=capture.content_type,
                    content=artifact.content if artifact else None,
                    failure=capture.failure,
                    http_status=capture.http_status,
                )
                for capture, artifact in rows
            ]
