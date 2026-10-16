"""Persistent monitoring and publication tests through the actual API/storage path."""

import asyncio

from arbbot.arbitrage.engine import evaluate
from arbbot.discovery.service import CatalogService
from arbbot.domain import Match, utcnow
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.monitoring import PairMonitor
from arbbot.ingestion.pipeline import Pipeline


async def test_exploration_reserve_prevents_verified_pair_starvation(database, fixture_market):
    settings, _, repository = database
    settings = settings.model_copy(update={"discovery_limit": 5})
    originals, _, _, _ = fixture_market
    markets, matches = [], []
    for i in range(6):
        pair = [
            m.model_copy(
                update={
                    "id": f"{m.venue}:reserve-{i}",
                    "external_id": f"reserve-{i}",
                    "category": "Politics" if i == 5 else "Sports",
                }
            )
            for m in originals
        ]
        for market in pair:
            await repository.save_market(market)
        markets.extend(pair)
        matches.append(
            Match(
                id=f"reserve-{i}",
                mode="simulation",
                left_id=pair[0].id,
                right_id=pair[1].id,
                status="candidate" if i == 5 else "verified",
                similarity=0.1,
                reason="Allocation fixture only; no financial estimate is asserted.",
            )
        )
    await repository.publish("simulation", matches, [])
    selected = await PairMonitor(
        settings, repository, [SimulationAdapter(v) for v in ("kalshi", "polymarket")]
    ).select(markets)
    assert len(selected) == 10
    assert {m.venue for m in selected if m.external_id == "reserve-5"} == {"kalshi", "polymarket"}


async def test_pairs_rotate_together_and_resume(database, fixture_market):
    settings, _, repository = database
    settings = settings.model_copy(update={"discovery_limit": 1})
    original, _, _, _ = fixture_market
    markets, matches = [], []
    for i in range(3):
        pair = [
            m.model_copy(update={"id": f"{m.venue}:{i}", "external_id": str(i)}) for m in original
        ]
        markets.extend(pair)
        for m in pair:
            await repository.save_market(m)
        matches.append(
            Match(
                id=str(i),
                mode="simulation",
                left_id=pair[0].id,
                right_id=pair[1].id,
                status="candidate",
                similarity=1,
                reason="Test",
            )
        )
    await repository.publish("simulation", matches, [])
    adapters = [SimulationAdapter(v) for v in ("kalshi", "polymarket")]
    cohorts = []
    for _ in range(3):
        # Recreate allocator each tick, proving the offset survives restart.
        selected = await PairMonitor(settings, repository, adapters).select(markets)
        assert len(selected) == 2
        assert selected[0].external_id == selected[1].external_id
        cohorts.append(selected[0].external_id)
    assert len(set(cohorts)) == 3


async def test_pair_publication_preserves_unrelated_generation(database, fixture_market):
    settings, _, repository = database
    markets, books, _, match = fixture_market
    for market in markets:
        await repository.save_market(market)
        await repository.save_book(books[market.id])
    result = evaluate(match, *markets, books, settings, utcnow())
    await repository.publish("simulation", [match], [result])
    unrelated = match.model_copy(update={"id": "unrelated", "status": "candidate", "review": None})
    await repository.publish("simulation", [unrelated], [], replace_generation=False)
    assert {m.id for m in await repository.matches("simulation")} == {match.id, "unrelated"}
    assert len(await repository.opportunities("simulation", 120, history=True)) == 1
    # An empty evaluation cohort must not deactivate the existing calculation.
    from sqlalchemy import select

    from arbbot.storage.models import OpportunityRecord

    async with repository.database.sessions() as session:
        assert (await session.scalar(select(OpportunityRecord))).active


async def test_independent_matching_does_not_delay_quotes(database, fixture_market):
    settings, _, repository = database
    adapters = [SimulationAdapter(v) for v in ("kalshi", "polymarket")]
    catalog = CatalogService(settings, repository, adapters)
    markets = fixture_market[0]
    for m in markets:
        await repository.save_market(m)
    catalog.all_current = lambda venue: [m for m in markets if m.venue == venue]

    async def inventory(venue):
        return catalog.all_current(venue)

    catalog.inventory.markets = inventory
    pipeline = Pipeline(settings, repository, adapters, catalog=catalog)
    entered, release, quotes_ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_ingest = pipeline.ingest_venue

    async def matching(markets):
        entered.set()
        await release.wait()
        return []

    async def ingest(adapter, selected=None):
        result = await original_ingest(adapter, selected)
        if result[1]:
            quotes_ready.set()
        return result

    pipeline.match_catalog, pipeline.ingest_venue = matching, ingest
    stop = asyncio.Event()
    task = asyncio.create_task(pipeline.run(stop))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.wait_for(quotes_ready.wait(), 2)
        assert not release.is_set()
        assert await repository.latest_books("simulation")
    finally:
        stop.set()
        release.set()
        await asyncio.wait_for(task, 2)


async def test_smaller_venue_budget_does_not_split_known_pairs(database, fixture_market):
    settings, _, repository = database
    settings = settings.model_copy(update={"monitoring_limits": {"kalshi": 2, "polymarket": 1}})
    original = fixture_market[0]
    markets, matches = [], []
    for i in range(3):
        pair = [
            m.model_copy(update={"id": f"{m.venue}:PAIR-{i}", "external_id": f"PAIR-{i}"})
            for m in original
        ]
        markets.extend(pair)
        for market in pair:
            await repository.save_market(market)
        matches.append(
            Match(
                id=f"budget-{i}",
                mode="simulation",
                left_id=pair[0].id,
                right_id=pair[1].id,
                status="candidate",
                similarity=1,
                reason="Known candidate pair",
            )
        )
    await repository.publish("simulation", matches, [])
    selected = await PairMonitor(
        settings, repository, [SimulationAdapter(v) for v in ("kalshi", "polymarket")]
    ).select(markets)
    assert len(selected) == 2 and selected[0].external_id == selected[1].external_id
