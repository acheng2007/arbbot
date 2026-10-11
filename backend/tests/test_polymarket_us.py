import hashlib
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from arbbot.api.app import create_app
from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.discovery.models import EventFamily
from arbbot.domain import utcnow
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets

ROOT = Path(__file__).parent / "fixtures/us_venues"


def recorded(name):
    return json.loads((ROOT / name).read_text(), parse_float=str)


def pair():
    return [
        KalshiAdapter.normalize_market(recorded("kalshi-dodgers.json")["market"]),
        PolymarketUSAdapter.normalize_market(recorded("polymarket-us-dodgers.json")["market"]),
    ]


def test_captured_evidence_is_immutable():
    for item in recorded("manifest.json"):
        assert hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest() == item["sha256"]
        assert item["status"] == 200


def test_recorded_outcomes_do_not_control_side_mapping():
    market = pair()[1]
    assert market.venue == "polymarket_us"
    assert market.tokens == {}
    assert market.settlement_asset == "USD"
    assert "Los Angeles Dodgers" in market.title
    book = PolymarketUSAdapter.normalize_book(market, recorded("polymarket-us-dodgers-book.json"))
    raw = book.raw["marketData"]
    assert book.yes_asks[0].price == min(Decimal(e["px"]["value"]) for e in raw["offers"])
    assert book.no_asks[0].price == 1 - max(Decimal(e["px"]["value"]) for e in raw["bids"])
    assert book.min_order_size == 1
    assert book.source_at is not None


@pytest.mark.parametrize(
    "change", ["identity", "halt", "currency", "negative", "fractional", "crossed", "timestamp"]
)
def test_invalid_books_fail_closed(change):
    market = pair()[1]
    payload = recorded("polymarket-us-dodgers-book.json")
    data = payload["marketData"]
    if change == "identity":
        data["marketSlug"] = "another-market"
    if change == "halt":
        data["state"] = "MARKET_STATE_HALTED"
    if change == "currency":
        data["offers"][0]["px"]["currency"] = "EUR"
    if change == "negative":
        data["offers"][0]["qty"] = "-1"
    if change == "fractional":
        data["offers"][0]["qty"] = "0.5"
    if change == "crossed":
        data["offers"][0]["px"]["value"] = "0.001"
    if change == "timestamp":
        data.pop("transactTime")
    with pytest.raises((ValueError, KeyError)):
        PolymarketUSAdapter.normalize_book(market, payload)


def test_championship_pair_is_rule_backed_but_not_approved():
    markets = pair()
    definitions = [extract_contract(m).definition for m in markets]
    matches = match_markets(markets, [], definitions)
    assert len(matches) == 1
    match = matches[0]
    assert match.comparison.same_event
    assert match.status == "candidate"
    assert match.comparison.status == "incomplete"
    result = evaluate(match, *markets, {}, Settings(_env_file=None), utcnow())
    assert not result.opportunities
    assert "polymarket_us_discovery_only:fees_rules_and_access_unverified" in result.blocked_reasons


def test_different_team_or_competition_never_gets_same_event():
    a, b = pair()
    for rules in [
        b.rules.replace("Los Angeles Dodgers", "Atlanta Braves"),
        b.rules.replace("MLB World Series", "National League pennant"),
        b.rules.replace("2026 MLB", "2027 MLB"),
    ]:
        other = b.model_copy(update={"rules": rules})
        matches = match_markets(
            [a, other], [], [extract_contract(m).definition for m in (a, other)]
        )
        assert not any(m.comparison.same_event for m in matches)


async def test_bounded_catalog_selects_world_series_only():
    calls = []

    async def respond(request):
        calls.append(request)
        return httpx.Response(200, json=recorded("polymarket-us-catalog.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = PolymarketUSAdapter(ExchangeHTTP(client, interval=0))
        family = EventFamily(
            name="mlb_champion",
            kalshi_series=("KXMLB",),
            polymarket_queries=("World Series",),
            keywords=("World Series",),
        )
        scan = await adapter.scan_catalog((family,), 20, 2)
    assert len(calls) == 2
    assert scan.truncated
    assert scan.markets
    assert all("World Series" in m.title for m in scan.markets)
    assert len({m.id for m in scan.markets}) == len(scan.markets)
    assert any(d.reason == "unrelated_event_family" for d in scan.decisions)


async def test_us_catalog_api_preserves_international_history_but_filters_active_venues(database):
    settings, db, repo = database
    settings = settings.model_copy(
        update={"mode": "live", "enabled_venues": ("kalshi", "polymarket_us")}
    )
    a, b = pair()
    historic = a.model_copy(update={"id": "polymarket:historic", "venue": "polymarket"})
    for market in (a, b, historic):
        await repo.save_market(market)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/markets")
        assert response.status_code == 200
        assert {m["venue"] for m in response.json()} == {"kalshi", "polymarket_us"}
        assert (await client.get("/api/v1/markets/polymarket:historic")).status_code == 200
        venues = (await client.get("/api/v1/venues")).json()
        assert next(v for v in venues if v["id"] == "polymarket_us")["evaluation_enabled"] is False
