import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote

from arbbot.domain import Book, Level, Market, utcnow
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.polymarket_sources import enrich_polymarket
from arbbot.sources.fetch import SourceFetcher

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def array(value):
    return json.loads(value) if isinstance(value, str) else value


class PolymarketAdapter:
    venue = "polymarket"

    def __init__(self, http: ExchangeHTTP, market_ids: list[str] | None = None):
        self.http = http
        self.source_fetcher = SourceFetcher()
        self.market_ids = market_ids or []

    async def discover(self, limit: int) -> list[Market]:
        if self.market_ids:
            result = []
            for market_id in self.market_ids[:limit]:
                item = await self.http.get(GAMMA + "/markets/" + quote(market_id, safe=""))
                if self.supported(item):
                    result.append(self.normalize_market(item))
            return result
        markets, cursor, seen = [], None, set()
        # Bound scan work even if many returned markets are unsupported.
        for _ in range(20):
            params = {"limit": min(100, limit), "closed": "false", "active": "true"}
            if cursor:
                params["after_cursor"] = cursor
            data = await self.http.get(GAMMA + "/markets/keyset", params=params)
            for item in data["markets"]:
                if not self.supported(item) or not item.get("acceptingOrders"):
                    continue
                markets.append(self.normalize_market(item))
                if len(markets) == limit:
                    return markets
            cursor = data.get("next_cursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        return markets

    @staticmethod
    def supported(item):
        outcomes = array(item.get("outcomes") or [])
        tokens = array(item.get("clobTokenIds") or [])
        return (
            bool(item.get("enableOrderBook"))
            and not item.get("negRisk")
            and bool(item.get("endDate"))
            and {str(o).lower() for o in outcomes} == {"yes", "no"}
            and len(outcomes) == len(tokens) == 2
        )

    @staticmethod
    def normalize_market(item: dict) -> Market:
        tokens = {
            outcome.lower(): token
            for outcome, token in zip(
                array(item["outcomes"]), array(item["clobTokenIds"]), strict=True
            )
        }
        return Market(
            id="polymarket:" + str(item["id"]),
            external_id=str(item["id"]),
            venue="polymarket",
            mode="live",
            title=item["question"],
            rules=item.get("description") or "",
            closes_at=datetime.fromisoformat(item["endDate"]),
            status="open"
            if item.get("active") and not item.get("closed") and item.get("acceptingOrders")
            else "closed",
            settlement_asset="pUSD",
            tokens=tokens,
            raw=item,
            observed_at=utcnow(),
            settlement_details={
                k: item.get(k)
                for k in (
                    "conditionId",
                    "resolutionSource",
                    "umaResolutionStatus",
                    "negRisk",
                    "feesEnabled",
                    "feeSchedule",
                    "orderMinSize",
                    "orderPriceMinTickSize",
                )
            },
        )

    async def enrich_sources(self, market, repository):
        return await enrich_polymarket(market, repository, self.source_fetcher)

    async def fetch_book(self, market: Market) -> Book:
        yes, no = await asyncio.gather(
            *(
                self.http.get(CLOB + "/book", params={"token_id": market.tokens[side]})
                for side in ("yes", "no")
            )
        )
        return self.normalize_book(market, yes, no)

    @staticmethod
    def normalize_book(market: Market, yes: dict, no: dict) -> Book:
        times = []
        for side, data in (("yes", yes), ("no", no)):
            if str(data["asset_id"]) != market.tokens[side]:
                raise ValueError("Order book token does not match requested outcome")
            if data.get("neg_risk"):
                raise ValueError("Negative-risk books are not supported")
            if not data.get("timestamp"):
                raise ValueError("Polymarket book timestamp is missing")
            times.append(datetime.fromtimestamp(int(data["timestamp"]) / 1000, UTC))
        if abs((times[0] - times[1]).total_seconds()) > 10:
            raise ValueError("Outcome order books are not synchronized")

        def asks(data):
            return tuple(
                sorted(
                    (
                        Level(price=str(level["price"]), size=str(level["size"]))
                        for level in data["asks"]
                    ),
                    key=lambda level: level.price,
                )
            )

        return Book(
            market_id=market.id,
            mode=market.mode,
            yes_asks=asks(yes),
            no_asks=asks(no),
            min_order_size=max(
                Decimal(str(yes["min_order_size"])), Decimal(str(no["min_order_size"]))
            ),
            source_at=min(times),
            received_at=utcnow(),
            raw={"yes": yes, "no": no},
        )
