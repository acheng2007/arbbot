"""Broad discovery retains raw exclusions and resumes independently of monitoring."""

import httpx
import pytest
from sqlalchemy import func, select

from arbbot.discovery.inventory import CatalogInventory
from arbbot.discovery.service import CatalogService
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.storage.models import CatalogInventoryRecord, CatalogObservationRecord
from tests.test_polymarket_us import recorded
from tests.test_targeted_discovery import raw_kalshi


@pytest.mark.parametrize("venue", ["kalshi", "polymarket_us"])
async def test_restart_resumes_raw_inventory_without_monitoring_cap(database, venue):
    settings, db, repository = database
    settings = settings.model_copy(
        update={
            "mode": "live",
            "discovery_mode": "broad",
            "discovery_limit": 1,
            "catalog_page_size": 2,
            "discovery_scan_pages": 1,
        }
    )
    requests = []

    def item(identifier, supported=True):
        if venue == "kalshi":
            return raw_kalshi(
                identifier,
                market_type="binary" if supported else "scalar",
                close_time="2099-01-01T00:00:00Z",
            )
        raw = recorded("polymarket-us-dodgers.json")["market"]
        raw.update(
            slug=identifier,
            endDate="2099-01-01T00:00:00Z",
            category="elections",
            sportsMarketTypeV2=None,
        )
        for side in raw["marketSides"]:
            side["identifier"] = identifier
        if not supported:
            raw["marketType"] = "unfamiliar_variable_payout"
        return raw

    def handler(request):
        requests.append(request)
        second = (
            request.url.params.get("cursor") == "next"
            if venue == "kalshi"
            else request.url.params.get("offset") == "2"
        )
        values = [item("C")] if second else [item("A"), item("B", False)]
        return httpx.Response(200, json={"markets": values, "cursor": "" if second else "next"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = (
            KalshiAdapter(ExchangeHTTP(client, interval=0), settings)
            if venue == "kalshi"
            else PolymarketUSAdapter(ExchangeHTTP(client, interval=0))
        )
        first = await CatalogInventory(settings, repository).scan(adapter)
        assert first.truncated and len(first.markets) == 1
        second = await CatalogInventory(settings, repository).scan(adapter)
        assert not second.truncated and len(second.markets) == 2
        # Repeated content is idempotent, not discarded by the monitoring limit.
        await CatalogInventory(settings, repository).scan(adapter)
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(CatalogObservationRecord)) == 3
        rows = (await session.scalars(select(CatalogInventoryRecord))).all()
        assert len(rows) == 3
        rejected = next(row for row in rows if row.external_id == "B")
        assert not rejected.supported and rejected.reason
    assert len(requests) == 3


async def test_repeated_page_does_not_skip_ahead(database):
    settings, _, repository = database
    settings = settings.model_copy(
        update={"mode": "live", "catalog_page_size": 1, "discovery_scan_pages": 1}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"markets": [raw_kalshi()], "cursor": "next"})
        )
    ) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), settings)
        inventory = CatalogInventory(settings, repository)
        await inventory.scan(adapter)
        with pytest.raises(ValueError, match="did not advance"):
            await inventory.scan(adapter)
        assert (await inventory.progress("kalshi"))["continuation"] == "next"


async def test_catalog_service_separates_inventory_and_rotation(database):
    settings, _, repository = database
    settings = settings.model_copy(
        update={
            "mode": "live",
            "discovery_mode": "broad",
            "discovery_limit": 1,
            "catalog_page_size": 10,
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"markets": [raw_kalshi("A"), raw_kalshi("B")], "cursor": ""}
            )
        )
    ) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), settings)

        async def enrich(market, repository, fetcher):
            return market

        adapter.enrich_sources = enrich
        service = CatalogService(settings, repository, [adapter])
        first = await service.refresh(adapter)
        assert first.catalog_market_count == 2 and len(first.selected_market_ids) == 1
        assert len(service.all_current("kalshi")) == 2
        second = await service.refresh(adapter)
        assert first.selected_market_ids != second.selected_market_ids
        assert len(service.current("kalshi")) == 1


async def test_inventory_migration_preserves_existing_market_history(database, fixture_market):
    from arbbot.storage.models import Base
    from tests.test_catalog_migration import migrate

    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "head")
    markets, books, _, _ = fixture_market
    await repository.save_market(markets[0])
    await repository.save_book(books[markets[0].id])
    await migrate(settings, "downgrade", "b016_review_revisions")
    assert (await repository.market("simulation", markets[0].id)).terms_hash == markets[
        0
    ].terms_hash
    assert (await repository.book("simulation", markets[0].id)).id == books[markets[0].id].id
    await migrate(settings, "upgrade", "head")
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(CatalogObservationRecord)) == 0


@pytest.mark.parametrize("change", ["tick", "orientation", "quantity", "currency", "type"])
def test_structural_us_validation_rejects_unfamiliar_instruments(change):
    raw = recorded("polymarket-us-dodgers.json")["market"]
    if change == "tick":
        raw["orderPriceMinTickSize"] = "NaN"
    elif change == "orientation":
        raw["marketSides"][1]["long"] = True
    elif change == "quantity":
        raw["minimumTradeQty"] = "0"
    elif change == "currency":
        raw["marketSides"][0]["quote"]["currency"] = "EUR"
    else:
        raw["marketType"] = "scalar"
    with pytest.raises(ValueError):
        PolymarketUSAdapter.normalize_market(raw)


def test_election_instrument_keeps_native_short_semantics():
    raw = recorded("polymarket-us-dodgers.json")["market"]
    raw.update(category="elections", sportsMarketTypeV2=None)
    market = PolymarketUSAdapter.normalize_market(raw)
    assert market.category == "elections"
    assert market.execution_semantics.no_action == "short_instrument"
    assert market.execution_semantics.no_native_price_is_complement
    assert market.instrument_constraints.unit_payout == 1


async def test_inventory_api_exposes_unsupported_raw_provenance(database):
    from arbbot.api.app import create_app

    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live", "enabled_venues": ("kalshi",)})
    payload = raw_kalshi("UNSUPPORTED", market_type="scalar")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"markets": [payload], "cursor": ""})
        )
    ) as client:
        await CatalogInventory(settings, repository).scan(
            KalshiAdapter(ExchangeHTTP(client, interval=0), settings)
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        rows = (await client.get("/api/v1/catalog/inventory?supported=false")).json()
        assert len(rows) == 1 and rows[0]["reason"] == "unsupported_outcomes"
        assert rows[0]["raw"] == payload
        assert len(rows[0]["observation_id"]) == 64
        assert (await client.get("/api/v1/markets")).json() == []
