import asyncio
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from arbbot.sources.repository import SourceRepository
from arbbot.storage.models import Base, SourceArtifactRecord, SourceCaptureRecord
from tests.test_source_artifacts import capture_for

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
            "ARBBOT_DATABASE_URL": settings.database_url.get_secret_value(),
            "PYTHONPATH": str(ROOT / "backend"),
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, output.decode()


async def test_migration_roundtrip_and_immutable_evidence(database, fixture_market):
    settings, db, markets = database
    # The database fixture owns a temporary SQLite file or unique PostgreSQL schema.
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    market = fixture_market[0][0]
    await markets.save_market(market)
    sources = SourceRepository(db)
    capture = capture_for(market)
    await sources.capture(capture)
    await sources.capture(capture)
    for table in (SourceArtifactRecord, SourceCaptureRecord):
        for statement in (delete(table), update(table).values(url="https://example.com/altered")):
            with pytest.raises(DBAPIError, match="immutable"):
                async with db.sessions.begin() as session:
                    await session.execute(statement)
    assert (await sources.history(market.mode, market.id))[0].content == capture.content
    await migrate(settings, "downgrade", "a2a3099f82df")
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    assert await markets.market(market.mode, market.id) is not None
    await sources.capture(capture)
