import asyncio
import json
import logging

import httpx
from pydantic import TypeAdapter

from arbbot.arbitrage.engine import evaluate
from arbbot.domain import Review, utcnow
from arbbot.exchanges.simulation import simulation_reviews
from arbbot.matching.service import match_markets

logger = logging.getLogger(__name__)


def safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"exchange_http_{exc.response.status_code}"
    # Do not leak keys, connection strings, raw responses, or request headers.
    return type(exc).__name__


class Pipeline:
    def __init__(self, settings, repository, adapters):
        self.settings, self.repository, self.adapters = settings, repository, adapters

    async def ingest_venue(self, adapter):
        mode = self.settings.mode
        try:
            markets = await adapter.discover(self.settings.discovery_limit)
            markets = list({market.id: market for market in markets}.values())
            if not markets:
                await self.repository.set_health(
                    mode, adapter.venue, "degraded", error="no_supported_markets"
                )
                return [], {}
            semaphore = asyncio.Semaphore(8)

            async def fetch(market):
                if market.status != "open" or market.closes_at <= utcnow():
                    return None
                async with semaphore:
                    try:
                        return await adapter.fetch_book(market)
                    except Exception as exc:
                        return exc

            for market in markets:
                if market.mode != mode or market.venue != adapter.venue:
                    raise ValueError("Adapter emitted data for the wrong mode or venue")
                await self.repository.save_market(market)
            results = await asyncio.gather(*(fetch(market) for market in markets))
            books, errors = {}, []
            for market, result in zip(markets, results, strict=True):
                if result is None:
                    continue
                if isinstance(result, Exception):
                    errors.append(safe_error(result))
                elif result.market_id != market.id or result.mode != mode:
                    errors.append("book_identity_mismatch")
                elif await self.repository.save_book(result):
                    books[market.id] = result
                else:
                    errors.append("out_of_order_snapshot")
            status = "degraded" if errors else "healthy"
            await self.repository.set_health(
                mode,
                adapter.venue,
                status,
                len(markets),
                len(books),
                ",".join(sorted(set(errors))) if errors else None,
            )
            logger.info(
                "ingestion_cycle",
                extra={
                    "venue": adapter.venue,
                    "status": status,
                    "market_count": len(markets),
                    "book_count": len(books),
                },
            )
            # Conservative venue-level suppression until a complete healthy cycle.
            return markets, {} if errors else books
        except Exception as exc:
            error = safe_error(exc)
            logger.warning("ingestion_failed", extra={"venue": adapter.venue, "error": error})
            await self.repository.set_health(mode, adapter.venue, "degraded", error=error)
            return [], {}

    async def cycle(self):
        ingested = await asyncio.gather(*(self.ingest_venue(adapter) for adapter in self.adapters))
        markets = [market for discovered, _ in ingested for market in discovered]
        books = {key: value for _, snapshots in ingested for key, value in snapshots.items()}
        if self.settings.mode == "simulation":
            reviews = simulation_reviews(markets)
        elif self.settings.reviews_file:
            content = await asyncio.to_thread(self.settings.reviews_file.read_text)
            reviews = TypeAdapter(list[Review]).validate_python(json.loads(content))
        else:
            reviews = []
        matches = match_markets(markets, reviews)
        indexed = {market.id: market for market in markets}
        now = utcnow()
        # Calculation work must not block the event loop as the monitored set grows.
        evaluations = await asyncio.to_thread(
            lambda: [
                evaluate(
                    match,
                    indexed[match.left_id],
                    indexed[match.right_id],
                    books,
                    self.settings,
                    now,
                )
                for match in matches
            ]
        )
        await self.repository.publish(self.settings.mode, matches, evaluations)
        return {
            "mode": self.settings.mode,
            "markets": len(markets),
            "books": len(books),
            "matches": len(matches),
            "opportunities": sum(len(e.opportunities) for e in evaluations),
        }
