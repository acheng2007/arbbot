import pytest

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
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db", _env_file=None)
    db = Database(settings)
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield settings, db, Repository(db)
    await db.close()
