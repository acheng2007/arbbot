import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import select

from arbbot.domain import utcnow
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from arbbot.storage.models import Base, MarketRecord

ROOT = Path(__file__).resolve().parents[2]


async def migrate(settings, *args):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ROOT / "backend/alembic.ini"),
        *args,
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "backend"),
            "ARBBOT_DATABASE_URL": settings.database_url.get_secret_value(),
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, output.decode()


async def test_catalog_migration_roundtrip(database, fixture_market):
    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "head")
    market = fixture_market[0][0].model_copy(update={"title": "US CPI for August 2026"})
    await repository.save_market(market)
    sources = SourceRepository(db)
    evidence = await sources.record(
        SourceCapture(
            venue=market.venue,
            mode=market.mode,
            market_id=market.id,
            url="https://example.com/rules",
            label="resolution_source",
            content=b"Original settlement terms",
            content_type="text/plain",
            retrieved_at=utcnow(),
        )
    )
    await migrate(settings, "check")
    await migrate(settings, "downgrade", "d0cc5e73c848")
    assert await sources.artifacts(market.mode, market.id) == [evidence]
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    assert await sources.artifacts(market.mode, market.id) == [evidence]
    async with db.sessions() as session:
        assert (await session.scalar(select(MarketRecord))).family is None
    assert (await repository.market(market.mode, market.id)).terms_hash == market.terms_hash
    await repository.save_market(market)
    async with db.sessions() as session:
        assert (await session.scalar(select(MarketRecord))).family == "cpi"
