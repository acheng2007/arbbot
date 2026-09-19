import base64
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from arbbot.config import Settings
from arbbot.domain import utcnow
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket import PolymarketAdapter


def kalshi_market(ticker="DEMO"):
    return {
        "ticker": ticker,
        "market_type": "binary",
        "title": "Test event?",
        "status": "active",
        "close_time": (utcnow() + timedelta(days=1)).isoformat(),
        "rules_primary": "Test rules",
        "notional_value_dollars": "1.0000",
    }


def poly_market():
    return {
        "id": "123",
        "question": "Test event?",
        "description": "Test rules",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "outcomes": '["No", "Yes"]',
        "clobTokenIds": '["no-token", "yes-token"]',
        "endDate": (utcnow() + timedelta(days=1)).isoformat(),
        "negRisk": False,
    }


async def test_kalshi_cursor_pagination_and_complement_asks():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/orderbook"):
            return httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [["0.6100", "12.50"], ["0.6000", "20.00"]],
                        "no_dollars": [["0.5300", "9.00"], ["0.5200", "10.00"]],
                    }
                },
            )
        if request.url.params.get("cursor") == "next":
            return httpx.Response(200, json={"markets": [kalshi_market("TWO")], "cursor": ""})
        return httpx.Response(200, json={"markets": [kalshi_market()], "cursor": "next"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = KalshiAdapter(ExchangeHTTP(client, interval=0), Settings(_env_file=None))
        markets = await adapter.discover(2)
        assert len(markets) == 2
        book = await adapter.fetch_book(markets[0])
        assert book.yes_asks[0].price == Decimal("0.47")
        assert book.no_asks[0].price == Decimal("0.39")
        assert book.no_asks[0].size == Decimal("12.50")
        assert book.source_at is None
        assert calls[1].url.params["cursor"] == "next"


async def test_polymarket_uses_named_outcomes_and_actual_depth():
    def handler(request):
        if request.url.path.endswith("keyset"):
            return httpx.Response(200, json={"markets": [poly_market()], "next_cursor": None})
        return httpx.Response(
            200,
            json={
                "asset_id": request.url.params["token_id"],
                "timestamp": str(int(utcnow().timestamp() * 1000)),
                "asks": [{"price": "0.6", "size": "12"}, {"price": "0.4", "size": "5"}],
                "min_order_size": "5",
                "neg_risk": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = PolymarketAdapter(ExchangeHTTP(client, interval=0))
        market = (await adapter.discover(1))[0]
        assert market.tokens == {"yes": "yes-token", "no": "no-token"}
        book = await adapter.fetch_book(market)
        assert book.yes_asks[0].price == Decimal("0.4")
        assert book.min_order_size == Decimal("5")


async def test_polymarket_rejects_wrong_token_and_missing_timestamp():
    market = PolymarketAdapter.normalize_market(poly_market())
    book = {"asset_id": "wrong", "asks": [], "timestamp": "1000", "min_order_size": "5"}
    with pytest.raises(ValueError, match="token"):
        PolymarketAdapter.normalize_book(market, book, book)
    book["asset_id"] = "yes-token"
    book.pop("timestamp")
    with pytest.raises(ValueError, match="timestamp"):
        PolymarketAdapter.normalize_book(market, book, book)


async def test_rate_limits_retry_and_auth_failures_do_not(monkeypatch):
    calls = 0
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("arbbot.exchanges.base.asyncio.sleep", sleep)

    def handler(request):
        nonlocal calls
        calls += 1
        return (
            httpx.Response(429, headers={"Retry-After": "2"})
            if calls == 1
            else httpx.Response(200, json={"ok": True})
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await ExchangeHTTP(client, interval=0).get("https://example.test/book") == {
            "ok": True
        }
    assert calls == 2
    assert 2 in sleeps
    calls = 0

    def unauthorized(request):
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unauthorized)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await ExchangeHTTP(client, interval=0).get("https://example.test/book")
    assert calls == 1


def test_kalshi_signature_is_valid_and_private_key_stays_local(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "test.pem"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    adapter = KalshiAdapter(
        None, Settings(kalshi_key_id="test-key", kalshi_private_key_path=path, _env_file=None)
    )
    headers = adapter.headers("/markets/TEST/orderbook")
    message = (
        headers["KALSHI-ACCESS-TIMESTAMP"] + "GET/trade-api/v2/markets/TEST/orderbook"
    ).encode()
    key.public_key().verify(
        base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    assert "PRIVATE KEY" not in json.dumps(headers)
