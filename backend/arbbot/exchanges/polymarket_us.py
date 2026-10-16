"""Public Polymarket US data. Distinct from the International token exchange."""

from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

from arbbot.discovery.models import DiscoveryDecision, DiscoveryScan
from arbbot.domain import Book, ExecutionSemantics, InstrumentConstraints, Level, Market, utcnow
from arbbot.exchanges.polymarket_us_sources import enrich_polymarket_us

BASE = "https://gateway.polymarket.us"


class PolymarketUSAdapter:
    venue = "polymarket_us"

    def __init__(self, http, market_ids=None):
        self.http = http
        self.market_ids = market_ids or []  # Exact market slugs, never International IDs.

    @staticmethod
    def supported(item):
        sides = item.get("marketSides")
        if not isinstance(sides, list) or len(sides) != 2:
            return False
        # Explicit side metadata is authoritative; observed outcomes arrays can be reversed.
        return (
            bool(item.get("slug"))
            and bool(item.get("endDate"))
            and item.get("marketType")
            in {"futures", "binary", "moneyline", "spreads", "totals", "election"}
            and not item.get("assetPriceTerms")
            and not item.get("combo")
            and not item.get("negRisk")
            and {s.get("description", "").lower() for s in sides} == {"yes", "no"}
            and all(
                s.get("marketSideType") == "MARKET_SIDE_TYPE_INSTRUMENT"
                and s.get("identifier") == item["slug"]
                and s.get("long") is (s["description"].lower() == "yes")
                and (s.get("quote") or {}).get("currency") == "USD"
                for s in sides
            )
            and cls_constraints(item) is not None
        )

    @classmethod
    def normalize_market(cls, item):
        if not cls.supported(item):
            raise ValueError("Unsupported Polymarket US instrument or outcome mapping")
        return Market(
            id="polymarket_us:" + item["slug"],
            external_id=item["slug"],
            venue=cls.venue,
            mode="live",
            title=f"{item['question']}: {item['title']}",
            rules=item.get("description") or "",
            closes_at=datetime.fromisoformat(item["endDate"]),
            status="open"
            if item.get("active")
            and not item.get("closed")
            and item.get("status") == "MARKET_STATUS_OPEN"
            else "closed",
            settlement_asset="USD",
            category=item.get("category"),
            instrument_constraints=cls_constraints(item),
            execution_semantics=ExecutionSemantics(
                yes_action="buy_instrument",
                no_action="short_instrument",
                no_native_price_is_complement=True,
                gross_short_collateral_per_contract="1",
            ),
            observed_at=utcnow(),
            raw=item,
            settlement_details={
                "instrument": item["slug"],
                "outcome_mechanics": "YES buys the instrument; NO shorts it with full collateral",
                "minimum_trade_quantity": str(item["minimumTradeQty"]),
                "price_tick": str(item["orderPriceMinTickSize"]),
                "eligibility": "US account and product eligibility require verification",
            },
        )

    async def discover(self, limit):
        return list((await self.scan_catalog((), limit, 8)).markets)

    async def scan_catalog(self, families, limit, max_pages):
        import re

        markets, decisions, seen = [], [], set()
        pages, truncated = 0, False
        for page in range(max_pages):
            if self.market_ids:
                if page >= min(limit, len(self.market_ids)):
                    break
                slug = self.market_ids[page]
                data = await self.http.get(BASE + "/v1/market/slug/" + quote(slug, safe=""))
                items = [data["market"]]
                if items[0].get("slug") != slug:
                    raise ValueError("Market identity mismatch")
            else:
                data = await self.http.get(
                    BASE + "/v1/markets",
                    params={
                        "limit": 100,
                        "offset": page * 100,
                        "active": "true",
                        "closed": "false",
                    },
                )
                items = data["markets"]
            pages += 1
            if not isinstance(items, list) or len(items) > 1000:
                raise ValueError("Invalid bounded catalog response")
            for item in items:
                slug = item.get("slug", "")
                if slug in seen:
                    continue
                seen.add(slug)
                reason, market = None, None
                family = "watchlist" if self.market_ids else "catalog"
                try:
                    market = self.normalize_market(item)
                    if market.status != "open" or market.closes_at <= utcnow():
                        reason = "closed_or_expired"
                    if families and not self.market_ids:
                        found = next(
                            (
                                f
                                for f in families
                                if any(
                                    re.search(r"\b" + re.escape(term) + r"\b", market.title, re.I)
                                    for term in f.keywords
                                )
                            ),
                            None,
                        )
                        if found:
                            family = found.name
                        else:
                            reason = "unrelated_event_family"
                except (ValueError, KeyError, TypeError, ArithmeticError):
                    reason = "unsupported_or_invalid_instrument"
                if not reason and len(markets) >= limit:
                    reason, truncated = "catalog_limit_reached", True
                if not reason:
                    markets.append(market)
                decisions.append(
                    DiscoveryDecision(
                        external_id=slug,
                        family=family,
                        included=not bool(reason),
                        reason=reason or "event_family_candidate",
                    )
                )
                if len(decisions) >= 2000:
                    truncated = True
                    break
            if len(markets) >= limit or len(decisions) >= 2000:
                truncated = True
                break
            if not self.market_ids and len(items) < 100:
                break
        else:
            truncated = True
        return DiscoveryScan(
            markets=tuple(markets),
            decisions=tuple(decisions),
            pages_scanned=pages,
            truncated=truncated,
        )

    async def fetch_book(self, market):
        data = await self.http.get(
            BASE + "/v1/markets/" + quote(market.external_id, safe="") + "/book"
        )
        return self.normalize_book(market, data)

    @staticmethod
    def normalize_book(market, payload):
        data = payload["marketData"]
        if data["marketSlug"] != market.external_id or market.venue != "polymarket_us":
            raise ValueError("Book identity mismatch")
        if data.get("state") != "MARKET_STATE_OPEN":
            raise ValueError("Book is not open for trading")

        def levels(entries, complement=False):
            aggregate = {}
            for entry in entries:
                if entry["px"]["currency"] != "USD":
                    raise ValueError("Unsupported quote currency")
                price, size = Decimal(entry["px"]["value"]), Decimal(entry["qty"])
                Level(price=price, size=size)  # Validate before complementing or aggregating.
                constraints = market.instrument_constraints
                if constraints and (
                    size % constraints.quantity_increment != 0
                    or price % constraints.price_increment != 0
                ):
                    raise ValueError("Book violates instrument increments")
                if constraints is None and size != size.to_integral_value():
                    raise ValueError("Unsupported fractional contract quantity")
                price = 1 - price if complement else price
                aggregate[price] = aggregate.get(price, Decimal(0)) + size
            return tuple(Level(price=p, size=s) for p, s in sorted(aggregate.items()))

        yes = levels(data["offers"])
        no = levels(data["bids"], True)
        if yes and no and yes[0].price + no[0].price < 1:
            raise ValueError("Crossed order book")
        return Book(
            market_id=market.id,
            mode=market.mode,
            yes_asks=yes,
            no_asks=no,
            min_order_size=market.settlement_details["minimum_trade_quantity"],
            source_at=datetime.fromisoformat(data["transactTime"]),
            received_at=utcnow(),
            raw=payload,
        )

    async def enrich_sources(self, market, repository, fetcher):
        return await enrich_polymarket_us(market, repository, fetcher)


def cls_constraints(item):
    """Public gateway binary formats, backed by documented USD unit payout semantics."""
    try:
        tick = Decimal(str(item["orderPriceMinTickSize"]))
        if not tick.is_finite() or not 0 < tick <= 1:
            return None
        return InstrumentConstraints(
            price_increment=tick,
            quantity_increment=str(item["minimumTradeQty"]),
            minimum_quantity=str(item["minimumTradeQty"]),
            payout_evidence="https://docs.polymarket.us/concepts/events-and-markets",
        )
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return None
