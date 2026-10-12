"""Exercise persistent scheduler boundaries through storage and public API reads."""

import asyncio

import httpx

from arbbot.api.app import create_app
from arbbot.discovery.service import CatalogService
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from tests.test_targeted_discovery import raw_kalshi


async def test_background_catalog_does_not_wait_for_source_extraction(database):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live", "discovery_mode": "broad"})
    entered, release = asyncio.Event(), asyncio.Event()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"markets": [raw_kalshi("SCHEDULED")], "cursor": ""}
            )
        )
    ) as exchange:
        adapter = KalshiAdapter(ExchangeHTTP(exchange, interval=0), settings)

        async def slow_source(market, sources, fetcher):
            entered.set()
            await release.wait()
            return market

        adapter.enrich_sources = slow_source
        catalog = CatalogService(settings, repository, [adapter])
        task = asyncio.create_task(catalog.refresh(adapter, enrich=False))
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
            ) as api:
                report = await asyncio.wait_for(asyncio.shield(task), 1)
                assert report.selected_market_ids == ("kalshi:SCHEDULED",)
                assert catalog.current("kalshi")
                assert (await api.get("/api/v1/discovery")).json()[0]["catalog_market_count"] == 1
                assert not entered.is_set()
        finally:
            release.set()
            await task


async def test_focused_watchlist_worker_polls_persisted_contract(database):
    settings, db, repository = database
    settings = settings.model_copy(
        update={
            "mode": "live",
            "discovery_mode": "focused",
            "poll_seconds": 1,
            "enabled_venues": ("kalshi",),
            "kalshi_tickers": ["FOCUSED"],
        }
    )
    from arbbot.ingestion.pipeline import Pipeline

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [["0.5", "10.00"]],
                        "no_dollars": [["0.4", "10.00"]],
                    }
                }
                if request.url.path.endswith("orderbook")
                else {"market": raw_kalshi("FOCUSED")},
            )
        )
    ) as exchange:
        adapter = KalshiAdapter(ExchangeHTTP(exchange, interval=0), settings)

        async def enriched(market, sources, fetcher):
            return market

        adapter.enrich_sources = enriched
        catalog = CatalogService(settings, repository, [adapter])
        await catalog.refresh(adapter)
        stop = asyncio.Event()
        worker = asyncio.create_task(
            Pipeline(settings, repository, [adapter], catalog=catalog).run(stop)
        )
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
            ) as api:
                for _ in range(15):
                    response = await api.get("/api/v1/markets/kalshi:FOCUSED/book")
                    if response.status_code == 200:
                        break
                    await asyncio.sleep(0.1)
                assert response.status_code == 200
        finally:
            stop.set()
            await worker


async def test_unchanged_quotes_coalesce_evaluation_history(database, fixture_market):
    from arbbot.ingestion.pipeline import Pipeline

    settings, db, repository = database
    settings = settings.model_copy(update={"poll_seconds": 1})
    markets, books, _, _ = fixture_market

    class Adapter:
        def __init__(self, venue):
            self.venue = venue

        async def fetch_book(self, market):
            return books[market.id]

    adapters = [Adapter(v) for v in ("kalshi", "polymarket")]
    for market in markets:
        await repository.save_market(market)
    catalog = CatalogService(settings, repository, adapters)
    catalog.all_current = lambda venue: [m for m in markets if m.venue == venue]
    stop = asyncio.Event()
    worker = asyncio.create_task(
        Pipeline(settings, repository, adapters, catalog=catalog).run(stop)
    )
    try:
        await asyncio.sleep(2.2)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
        ) as api:
            rows = (await api.get("/api/v1/evaluations", params={"history": "true"})).json()
            assert sum(row["status"] == "profitable" for row in rows) == 1
            assert len(rows) <= 2  # Initial missing-book state may precede the first quote.
    finally:
        stop.set()
        await worker
