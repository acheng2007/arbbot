from decimal import Decimal

from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.domain import Level, utcnow
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.pipeline import Pipeline


async def test_market_terms_and_book_versions_remain_available(database, fixture_market):
    _, _, repository = database
    markets, books, _, _ = fixture_market
    old = markets[0]
    await repository.save_market(old)
    await repository.save_book(books[old.id])
    updated = old.model_copy(update={"rules": "New settlement terms", "observed_at": utcnow()})
    await repository.save_market(updated)
    assert (await repository.market("simulation", old.id)).terms_hash == updated.terms_hash
    historical = await repository.market_version("simulation", old.id, old.terms_hash)
    assert historical.rules == old.rules
    assert await repository.snapshot("simulation", books[old.id].id) == books[old.id]
    assert await repository.snapshot("live", books[old.id].id) is None


async def test_limit_order_funding_is_distinct_from_expected_outlay(fixture_market):
    markets, books, _, match = fixture_market
    books[markets[0].id] = books[markets[0].id].model_copy(
        update={"yes_asks": (Level(price="0.1", size="1"), Level(price="0.4", size="9"))}
    )
    result = evaluate(match, *markets, books, Settings(_env_file=None), utcnow())
    opportunity = result.opportunities[0]
    assert opportunity.quantity == 10
    assert opportunity.capital_required - opportunity.estimated_outlay == Decimal("0.30")
    assert opportunity.minimum_payout - opportunity.estimated_outlay == opportunity.net_profit
    limited = evaluate(
        match, *markets, books, Settings(max_capital="8.8", _env_file=None), utcnow()
    )
    assert limited.opportunities[0].quantity == 9


async def test_empty_exchange_clears_previous_opportunities(database):
    settings, _, repository = database
    adapters = [SimulationAdapter(venue) for venue in ("kalshi", "polymarket")]
    await Pipeline(settings, repository, adapters).cycle()

    class EmptyAdapter(SimulationAdapter):
        async def discover(self, limit):
            return []

    await Pipeline(settings, repository, [adapters[0], EmptyAdapter("polymarket")]).cycle()
    assert not await repository.opportunities(settings.mode, 120)
    assert len(await repository.opportunities(settings.mode, 120, history=True)) == 1
