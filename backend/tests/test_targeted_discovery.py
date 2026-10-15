import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from arbbot.api.app import create_app
from arbbot.config import Settings
from arbbot.discovery.models import EventFamily
from arbbot.discovery.service import CatalogService, CatalogUnavailable, catalog_reports
from arbbot.domain import utcnow
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.discovery import scan_catalog
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.ingestion.pipeline import Pipeline
from tests.test_adapters import kalshi_market, poly_market

FAMILY = EventFamily(
    name="cpi", kalshi_series=("KXCPI",), polymarket_queries=("CPI",), keywords=("CPI",)
)


@pytest.mark.parametrize(
    "venue,filename", [("kalshi", "kalshi-cpi.json"), ("polymarket", "polymarket-search.json")]
)
async def test_recorded_discovery_preserves_eligibility_and_reports_coverage(
    venue, filename, monkeypatch
):
    record = json.loads((Path(__file__).parent / "fixtures/discovery" / filename).read_text())
    monkeypatch.setattr(
        "arbbot.exchanges.discovery.utcnow", lambda: datetime.fromisoformat(record["recorded_at"])
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=record["response"]))
    ) as client:
        http = ExchangeHTTP(client, interval=0)
        adapter = (
            KalshiAdapter(http, Settings(_env_file=None))
            if venue == "kalshi"
            else PolymarketAdapter(http)
        )
        scan = await scan_catalog(adapter, (FAMILY,), 20, 1)
    if venue == "kalshi":
        assert len(scan.markets) == 5 and scan.truncated
        assert all(m.external_id.startswith("KXCPI-") for m in scan.markets)
    else:
        assert not scan.markets
        assert {d.reason for d in scan.decisions} == {
            "unsupported_negative_risk",
            "unrelated_event_family",
        }


def raw_kalshi(ticker="CPI-ONE", **changes):
    return {**kalshi_market(ticker), "title": "US CPI for September 2026", **changes}


def raw_poly(identifier="123", **changes):
    return {**poly_market(), "id": identifier, "question": "US CPI for September 2026", **changes}


async def test_kalshi_targeted_pagination_duplicates_and_exclusions():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.params.get("cursor") == "next":
            return httpx.Response(
                200, json={"markets": [raw_kalshi(), raw_kalshi("CPI-TWO")], "cursor": ""}
            )
        return httpx.Response(
            200,
            json={
                "markets": [
                    raw_kalshi(),
                    raw_kalshi("OTHER", title="A football match"),
                    raw_kalshi("SCALAR", market_type="scalar"),
                    raw_kalshi("CLOSED", status="settled"),
                    raw_kalshi("NOTIONAL", notional_value_dollars="100"),
                ],
                "cursor": "next",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), Settings(_env_file=None))
        scan = await scan_catalog(adapter, (FAMILY,), 10, 3)
    assert [m.external_id for m in scan.markets] == ["CPI-ONE", "CPI-TWO"]
    assert scan.pages_scanned == 2 and not scan.truncated
    assert {d.reason for d in scan.decisions} == {
        "event_family_candidate",
        "unrelated_event_family",
        "unsupported_outcomes",
        "closed_or_expired",
        "unsupported_payout",
    }
    assert all(r.url.params["series_ticker"] == "KXCPI" for r in requests)


async def test_polymarket_search_pages_reject_negative_risk_and_wrong_family():
    requests = []

    def handler(request):
        requests.append(request)
        second = request.url.params["page"] == "2"
        markets = (
            [raw_poly("456")]
            if second
            else [
                raw_poly(),
                raw_poly("NEG", negRisk=True),
                raw_poly("SPORT", question="Will a football team win?"),
                raw_poly(
                    "BEEF",
                    question="Will ground beef hit $7 per pound?",
                    description="Settles using a price series from the US CPI report.",
                ),
                raw_poly("CLOSED", closed=True),
            ]
        )
        return httpx.Response(
            200, json={"events": [{"markets": markets}], "pagination": {"hasMore": not second}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = PolymarketAdapter(ExchangeHTTP(client, interval=0))
        scan = await scan_catalog(adapter, (FAMILY,), 10, 3)
    assert len(scan.markets) == 2 and not scan.truncated
    assert {d.reason for d in scan.decisions} >= {
        "unsupported_negative_risk",
        "unrelated_event_family",
        "closed_or_expired",
    }
    assert [r.url.params["page"] for r in requests] == ["1", "2"]
    assert all(r.url.path == "/public-search" and r.url.params["q"] == "CPI" for r in requests)


@pytest.mark.parametrize("venue", ["kalshi", "polymarket"])
async def test_watchlist_precedence_identity_and_unsupported_reporting(venue):
    requests = []

    def handler(request):
        requests.append(request)
        if venue == "kalshi":
            return httpx.Response(
                200, json={"market": raw_kalshi("EXACT", title="Outside configured family")}
            )
        return httpx.Response(200, json=raw_poly("EXACT", negRisk=True))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http = ExchangeHTTP(client, interval=0)
        adapter = (
            KalshiAdapter(http, Settings(kalshi_tickers=["EXACT", "EXACT"], _env_file=None))
            if venue == "kalshi"
            else PolymarketAdapter(http, ["EXACT", "EXACT"])
        )
        scan = await scan_catalog(adapter, (FAMILY,), 10, 3)
    assert len(requests) == 1 and requests[0].url.path.endswith("/markets/EXACT")
    assert scan.decisions[0].family == "watchlist"
    assert scan.decisions[0].reason == (
        "explicit_watchlist" if venue == "kalshi" else "unsupported_negative_risk"
    )


async def test_scan_budget_and_repeated_cursor_are_reported():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"markets": [], "cursor": "repeat"})
        )
    ) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), Settings(_env_file=None))
        scan = await scan_catalog(adapter, (FAMILY,), 10, 1)
        assert scan.truncated and scan.pages_scanned == 1
        scan = await scan_catalog(adapter, (FAMILY,), 10, 10)
        assert scan.truncated and scan.pages_scanned == 2


async def test_searches_share_catalog_budget():
    families = (FAMILY.model_copy(update={"kalshi_series": ("KXCPI", "KXCPIYOY")}),)

    def handler(request):
        series = request.url.params["series_ticker"]
        return httpx.Response(
            200, json={"markets": [raw_kalshi(f"{series}-{i}") for i in range(10)], "cursor": ""}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), Settings(_env_file=None))
        scan = await scan_catalog(adapter, families, 4, 4)
    assert len(scan.markets) == 4 and scan.pages_scanned == 2 and scan.truncated
    assert sum(m.external_id.startswith("KXCPIYOY") for m in scan.markets) == 2


async def test_catalog_refresh_is_independent_of_quotes_and_expires(
    database, fixture_market, monkeypatch
):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live", "discovery_families": (FAMILY,)})
    entered, release = asyncio.Event(), asyncio.Event()
    fail = False

    class Adapter:
        venue = "kalshi"
        tickers = []

        async def enrich_sources(self, market, sources, fetcher):
            return market.model_copy(
                update={
                    "settlement_details": {
                        "source_status": "incomplete",
                        "source_issues": ["missing_test_source"],
                    }
                }
            )

        async def fetch_book(self, market):
            return next(iter(fixture_market[1].values())).model_copy(
                update={
                    "mode": "live",
                    "market_id": market.id,
                    "received_at": utcnow(),
                    "source_at": utcnow(),
                }
            )

    async def handler(request):
        if fail:
            raise httpx.ConnectError("secret network details")
        if entered.is_set():
            await release.wait()
        entered.set()
        return httpx.Response(200, json={"markets": [raw_kalshi()], "cursor": ""})

    adapter = Adapter()
    adapter.normalize_market = KalshiAdapter.normalize_market
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter.http = ExchangeHTTP(client, interval=0)
        service = CatalogService(settings, repository, [adapter])
        first = await service.refresh(adapter)
        assert first.status == "degraded" and first.missing_source_market_ids == ("kalshi:CPI-ONE",)
        refresh = asyncio.create_task(service.refresh(adapter))
        await asyncio.sleep(0)
        pipeline = Pipeline(settings, repository, [adapter], catalog=service)
        # The catalog request is held open; quotes must still complete promptly.
        result = await asyncio.wait_for(pipeline.cycle(), timeout=2)
        assert result["books"] == 1 and not refresh.done()
        release.set()
        await refresh
        report = (await catalog_reports(db, "live"))[0]
        assert report.selected_market_ids == first.selected_market_ids
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
        ) as api:
            response = await api.get("/api/v1/discovery")
            assert response.status_code == 200
            assert response.json()[0]["missing_source_market_ids"] == ["kalshi:CPI-ONE"]
        assert await catalog_reports(db, "simulation") == []
        fail = True
        failed = await service.refresh(adapter)
        assert failed.status == "failed"
        assert "secret" not in failed.model_dump_json()
        assert service.current("kalshi")
        monkeypatch.setattr(
            "arbbot.discovery.service.utcnow", lambda: report.valid_until + timedelta(seconds=1)
        )
        with pytest.raises(CatalogUnavailable):
            service.current("kalshi")
        assert (await catalog_reports(db, "live"))[0].status == "stale"
        assert (await pipeline.cycle())["books"] == 0


async def test_scheduler_cancels_inflight_work(database):
    settings, _, repository = database

    class Adapter:
        venue = "kalshi"

    service = CatalogService(settings, repository, [Adapter()])
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def refresh(adapter, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    service.refresh = refresh
    service.start()
    await asyncio.wait_for(started.wait(), 1)
    await service.aclose()
    assert stopped.is_set() and not service.tasks
