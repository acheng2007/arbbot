"""Append-only repository interface for source evidence and retrieval failures."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from arbbot.domain import Mode
from arbbot.sources.models import SourceCapture
from arbbot.storage.models import MarketRecord, SourceArtifactRecord
from arbbot.storage.repository import aware


class SourceRepository:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def restore(row: SourceArtifactRecord) -> SourceCapture:
        return SourceCapture.model_validate(
            {**row.payload, "content": row.content, "retrieved_at": aware(row.retrieved_at)}
        )

    async def save(self, capture: SourceCapture) -> SourceCapture:
        # Validate again at the persistence boundary, including model_copy inputs.
        capture = SourceCapture.model_validate(capture.model_dump())
        async with self.database.sessions.begin() as session:
            market_key = f"{capture.mode}:{capture.market_id}"
            market = await session.get(MarketRecord, market_key)
            if market is None or market.venue != capture.venue:
                raise ValueError(
                    "Source capture requires a persisted market in the same mode/venue"
                )
            dialect = self.database.engine.dialect.name
            if dialect not in {"postgresql", "sqlite"}:
                raise ValueError("Source storage supports PostgreSQL and SQLite")
            insert = postgres_insert if dialect == "postgresql" else sqlite_insert
            await session.execute(
                insert(SourceArtifactRecord)
                .values(
                    id=capture.id,
                    market_key=market_key,
                    retrieved_at=capture.retrieved_at,
                    content_digest=capture.content_digest,
                    content=capture.content,
                    payload=capture.model_dump(mode="json", exclude={"content", "retrieved_at"}),
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            row = await session.get(SourceArtifactRecord, capture.id)
            return self.restore(row)

    async def history(
        self, mode: Mode, market_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[SourceCapture]:
        if not 1 <= limit <= 200 or not 0 <= offset <= 100000:
            raise ValueError("Invalid source history pagination")
        async with self.database.sessions() as session:
            rows = await session.scalars(
                select(SourceArtifactRecord)
                .where(SourceArtifactRecord.market_key == f"{mode}:{market_id}")
                .order_by(SourceArtifactRecord.retrieved_at.desc(), SourceArtifactRecord.id)
                .limit(limit)
                .offset(offset)
            )
            return [self.restore(row) for row in rows]
