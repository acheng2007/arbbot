import asyncio

import httpx

from arbbot.config import Settings
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.discovery import candidate
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets


async def main():
    async with httpx.AsyncClient(timeout=20) as client:
        http = ExchangeHTTP(client, interval=0.2)
        us = PolymarketUSAdapter(http)
        data = await http.get(
            "https://gateway.polymarket.us/v1/markets",
            params={"limit": 100, "offset": 0, "active": "true", "closed": "false"},
        )
        supported, excluded = [], 0
        for raw in data["markets"]:
            try:
                supported.append(us.normalize_market(raw))
            except (ValueError, KeyError, TypeError):
                excluded += 1
        print(
            {
                "observed": len(data["markets"]),
                "supported": len(supported),
                "excluded": excluded,
                "categories": sorted({m.category for m in supported if m.category}),
            }
        )
        if not supported:
            raise RuntimeError("No supported public instruments")
        market = next((m for m in supported if "World Series" in m.title), supported[0])
        book = await us.fetch_book(market)
        print(
            {
                "venue": market.venue,
                "market": market.id,
                "yes_levels": len(book.yes_asks),
                "no_levels": len(book.no_asks),
                "source_at": str(book.source_at),
            }
        )
        checked_us = {market.id}
        live_us = supported.copy()
        kalshi = KalshiAdapter(http, Settings(_env_file=None))
        data = await http.get(
            "https://external-api.kalshi.com/trade-api/v2/markets",
            params={"status": "open", "limit": 100, "mve_filter": "exclude"},
        )
        print(
            {"kalshi_observed": len(data["markets"]), "has_continuation": bool(data.get("cursor"))}
        )
        live_kalshi = []
        for raw_market in data["markets"]:
            reason, normalized = candidate(kalshi, raw_market, None)
            if not reason and normalized:
                live_kalshi.append(normalized)
        raw = await http.get("https://external-api.kalshi.com/trade-api/v2/markets/KXMLB-26-LAD")
        market = kalshi.normalize_market(raw["market"])
        book = await kalshi.fetch_book(market)
        print(
            {
                "venue": market.venue,
                "market": market.id,
                "yes_levels": len(book.yes_asks),
                "no_levels": len(book.no_asks),
                "source_at": str(book.source_at),
            }
        )

        raw_us = await http.get(
            "https://gateway.polymarket.us/v1/market/slug/tec-mlb-champ-2026-09-27-lad"
        )
        counterpart = us.normalize_market(raw_us["market"])
        pair = [market, counterpart]
        matches = match_markets(pair, [], [extract_contract(m).definition for m in pair])
        print(
            {
                "real_matches": [
                    {
                        "id": m.id,
                        "status": m.status,
                        "same_event": bool(m.comparison and m.comparison.same_event),
                        "reason": m.reason,
                        "issues": m.comparison.issues if m.comparison else (),
                    }
                    for m in matches
                ]
            }
        )

        checked_kalshi = {market.id}
        extra_books = []
        for adapter, catalog, checked in (
            (us, live_us, checked_us),
            (kalshi, live_kalshi, checked_kalshi),
        ):
            for instrument in catalog:
                if len(checked) >= 3:
                    break
                if instrument.id in checked or instrument.status != "open":
                    continue
                quote = await adapter.fetch_book(instrument)
                checked.add(instrument.id)
                extra_books.append(
                    {
                        "venue": instrument.venue,
                        "market": instrument.id,
                        "yes_levels": len(quote.yes_asks),
                        "no_levels": len(quote.no_asks),
                        "source_at": str(quote.source_at),
                    }
                )
        print(
            {
                "additional_books": extra_books,
                "books_checked_per_venue": {
                    "kalshi": len(checked_kalshi),
                    "polymarket_us": len(checked_us),
                },
            }
        )


asyncio.run(main())
