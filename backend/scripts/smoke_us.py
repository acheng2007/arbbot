import asyncio

import httpx

from arbbot.config import Settings
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter


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
        kalshi = KalshiAdapter(http, Settings(_env_file=None))
        data = await http.get(
            "https://external-api.kalshi.com/trade-api/v2/markets",
            params={"status": "open", "limit": 10},
        )
        print(
            {"kalshi_observed": len(data["markets"]), "has_continuation": bool(data.get("cursor"))}
        )
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


asyncio.run(main())
