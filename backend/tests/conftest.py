import os
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from arbbot.config import Settings
from arbbot.exchanges.simulation import SimulationAdapter, simulation_reviews
from arbbot.matching.service import match_markets
from arbbot.storage.database import Database
from arbbot.storage.models import Base
from arbbot.storage.repository import Repository


@pytest.fixture
async def fixture_market():
    adapters = [SimulationAdapter(venue) for venue in ("kalshi", "polymarket")]
    markets = [(await adapter.discover(1))[0] for adapter in adapters]
    books = {
        market.id: await adapter.fetch_book(market)
        for adapter, market in zip(adapters, markets, strict=True)
    }
    review = simulation_reviews(markets)[0]
    match = match_markets(markets, [review])[0]
    return markets, books, review, match


@pytest.fixture
async def database(tmp_path):
    postgres_url = os.environ.get("ARBBOT_TEST_DATABASE_URL")
    admin = None
    schema = "arbbot_test_" + uuid4().hex
    if postgres_url:
        url = make_url(postgres_url)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("ARBBOT_TEST_DATABASE_URL must use postgresql+psycopg")
        admin = Database(Settings(database_url=postgres_url, _env_file=None))
        async with admin.engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        database_url = url.update_query_dict(
            {"options": f"-csearch_path={schema}"}
        ).render_as_string(hide_password=False)
    else:
        database_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    # Existing review-path tests deliberately exercise historical compatibility.
    # Automatic qualification integration tests explicitly enable the new default.
    settings = Settings(database_url=database_url, automatic_qualification=False, _env_file=None)
    db = Database(settings)
    try:
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield settings, db, Repository(db)
    finally:
        await db.close()
        if admin:
            try:
                async with admin.engine.begin() as connection:
                    await connection.execute(DropSchema(schema, cascade=True))
            finally:
                await admin.close()
