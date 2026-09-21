import base64
import time
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from arbbot.config import Settings
from arbbot.domain import Book, Level, Market, utcnow
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi_sources import enrich_kalshi
from arbbot.sources.fetch import SourceFetcher

BASE = "https://external-api.kalshi.com/trade-api/v2"


class KalshiAdapter:
    venue = "kalshi"

    def __init__(self, http: ExchangeHTTP, settings: Settings):
        self.http = http
        self.source_fetcher = SourceFetcher()
        self.key_id = settings.kalshi_key_id
        self.tickers = settings.kalshi_tickers
        self.private_key = None
        if settings.kalshi_private_key_path:
            self.private_key = serialization.load_pem_private_key(
                settings.kalshi_private_key_path.read_bytes(), password=None
            )
            if not isinstance(self.private_key, rsa.RSAPrivateKey):
                raise ValueError("Kalshi requires an RSA private key")

    def headers(self, path: str) -> dict:
        if not self.key_id or not self.private_key:
            return {}
        stamp = str(time.time_ns() // 1_000_000)
        signature = self.private_key.sign(
            (stamp + "GET" + "/trade-api/v2" + path).encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id.get_secret_value(),
            "KALSHI-ACCESS-TIMESTAMP": stamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        }

    async def discover(self, limit: int) -> list[Market]:
        if self.tickers:
            markets = []
            for ticker in self.tickers[:limit]:
                data = await self.http.get(BASE + "/markets/" + quote(ticker, safe=""))
                item = data["market"]
                if (
                    item.get("market_type") == "binary"
                    and Decimal(str(item.get("notional_value_dollars", "1"))) == 1
                ):
                    markets.append(self.normalize_market(item))
            return markets
        markets, cursor, seen = [], "", set()
        for _ in range(20):
            data = await self.http.get(
                BASE + "/markets",
                params={
                    "limit": min(100, limit - len(markets)),
                    "cursor": cursor,
                    "status": "open",
                    "mve_filter": "exclude",
                },
            )
            for item in data["markets"]:
                if item.get("market_type") != "binary":
                    continue
                # Nonstandard notional payouts require a different normalization model.
                if Decimal(str(item.get("notional_value_dollars", "1"))) != 1:
                    continue
                markets.append(self.normalize_market(item))
            cursor = data.get("cursor", "")
            if len(markets) >= limit or not cursor or cursor in seen:
                break
            seen.add(cursor)
        return markets[:limit]

    @staticmethod
    def normalize_market(item: dict) -> Market:
        return Market(
            id="kalshi:" + item["ticker"],
            external_id=item["ticker"],
            venue="kalshi",
            mode="live",
            title=item.get("title") or item["yes_sub_title"],
            rules="\n".join(filter(None, (item.get("rules_primary"), item.get("rules_secondary")))),
            closes_at=datetime.fromisoformat(item["close_time"]),
            status="open" if item["status"] in {"open", "active"} else "closed",
            settlement_asset="USD",
            raw=item,
            observed_at=utcnow(),
            settlement_details={
                k: item.get(k)
                for k in (
                    "event_ticker",
                    "yes_sub_title",
                    "no_sub_title",
                    "strike_type",
                    "floor_strike",
                    "cap_strike",
                    "functional_strike",
                    "custom_strike",
                    "can_close_early",
                    "early_close_condition",
                    "expiration_time",
                    "latest_expiration_time",
                    "notional_value_dollars",
                    "settlement_timer_seconds",
                )
            },
        )

    async def enrich_sources(self, market, repository):
        return await enrich_kalshi(market, repository, self.source_fetcher)

    async def fetch_book(self, market: Market) -> Book:
        path = f"/markets/{quote(market.external_id, safe='')}/orderbook"
        data = await self.http.get(
            BASE + path, params={"depth": 0}, headers=lambda: self.headers(path)
        )
        return self.normalize_book(market, data)

    @staticmethod
    def normalize_book(market: Market, data: dict) -> Book:
        bids = data["orderbook_fp"]

        def asks(side):
            levels = [
                Level(price=Decimal(1) - Decimal(str(p)), size=str(q))
                for p, q in (bids.get(side) or [])
            ]
            return tuple(sorted(levels, key=lambda level: level.price))

        return Book(
            market_id=market.id,
            mode=market.mode,
            yes_asks=asks("no_dollars"),
            no_asks=asks("yes_dollars"),
            received_at=utcnow(),
            source_at=None,
            raw=data,
        )
