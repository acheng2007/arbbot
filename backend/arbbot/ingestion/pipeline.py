import asyncio
import json
import logging
from datetime import timedelta

import httpx
from pydantic import TypeAdapter

from arbbot.arbitrage.engine import evaluate
from arbbot.domain import MarketHealth, Review, utcnow
from arbbot.exchanges.simulation import simulation_reviews
from arbbot.matching.contracts import ContractDefinition
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets
from arbbot.observability.tracing import Tracing
from arbbot.quality import book_issue
from arbbot.reviews.provider import ReviewProvider
from arbbot.sources.fetch import SourceFetcher
from arbbot.sources.repository import SourceRepository

logger = logging.getLogger(__name__)


def safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"exchange_http_{exc.response.status_code}"
    # Do not leak keys, connection strings, raw responses, or request headers.
    return type(exc).__name__


class Pipeline:
    def __init__(
        self, settings, repository, adapters, tracing=None, source_fetcher=None, catalog=None
    ):
        self.settings, self.repository, self.adapters = settings, repository, adapters
        self.tracing = tracing or Tracing()
        self.sources = SourceRepository(repository.database, settings.source_max_bytes)
        self.source_fetcher = source_fetcher or SourceFetcher(max_bytes=settings.source_max_bytes)
        self.catalog = catalog
        self.review_provider = ReviewProvider(repository.database)

    async def ingest_venue(self, adapter):
        mode = self.settings.mode
        try:
            with self.tracing.span("ingestion.catalog", venue=adapter.venue) as span:
                markets = (
                    self.catalog.current(adapter.venue)
                    if self.catalog is not None
                    else await adapter.discover(self.settings.discovery_limit)
                )
                span.set_attribute("market_count", len(markets))
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
                        with self.tracing.span("ingestion.book", venue=adapter.venue):
                            return await adapter.fetch_book(market)
                    except Exception as exc:
                        return exc

            for market in markets:
                if market.mode != mode or market.venue != adapter.venue:
                    raise ValueError("Adapter emitted data for the wrong mode or venue")
                if self.catalog is None:
                    await self.repository.save_market(market)
            if self.catalog is None and mode == "live" and hasattr(adapter, "enrich_sources"):

                async def enrich(market):
                    async with semaphore:
                        with self.tracing.span("ingestion.sources", venue=adapter.venue):
                            return await adapter.enrich_sources(
                                market, self.sources, self.source_fetcher
                            )

                markets = await asyncio.gather(*(enrich(market) for market in markets))
                for market in markets:
                    await self.repository.save_market(market)
            results = await asyncio.gather(*(fetch(market) for market in markets))
            books, errors, market_health = {}, [], []
            for market, result in zip(markets, results, strict=True):
                now = utcnow()
                issue = None
                details = {}
                if market.status != "open" or market.closes_at <= now:
                    feed_status = "closed"
                elif isinstance(result, Exception):
                    issue = safe_error(result)
                    feed_status = "error"
                else:
                    issue = book_issue(market, result, now, self.settings.max_quote_age_seconds)
                    # Keep old snapshots for audit, but never persist a wrong-identity or
                    # future-dated book as the latest snapshot for an otherwise valid market.
                    if result is not None and issue in (None, "book_stale"):
                        if not await self.repository.save_book(result):
                            issue = "out_of_order_snapshot"
                        else:
                            details = {
                                "book_id": result.id,
                                "quote_at": result.effective_at,
                                "valid_until": result.effective_at
                                + timedelta(seconds=self.settings.max_quote_age_seconds),
                            }
                    feed_status = (
                        "stale" if issue == "book_stale" else "error" if issue else "healthy"
                    )
                    if not issue:
                        books[market.id] = result
                if issue:
                    errors.append(issue)
                market_health.append(
                    MarketHealth(
                        market_id=market.id,
                        status=feed_status,
                        checked_at=now,
                        error=issue,
                        **details,
                    )
                )
            status = "degraded" if errors else "healthy"
            await self.repository.set_health(
                mode,
                adapter.venue,
                status,
                len(markets),
                len(books),
                ",".join(sorted(set(errors))) if errors else None,
                market_health=market_health,
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
            # Failed markets remain visible in health, without discarding unrelated books.
            return markets, books
        except Exception as exc:
            error = safe_error(exc)
            logger.warning("ingestion_failed", extra={"venue": adapter.venue, "error": error})
            await self.repository.set_health(mode, adapter.venue, "degraded", error=error)
            return [], {}

    async def cycle(self):
        with self.tracing.span("ingestion.cycle", root=True, mode=self.settings.mode) as span:
            result = await self._cycle()
            for key in ("markets", "books", "matches", "opportunities"):
                span.set_attribute(key, result[key])
            return result

    async def _cycle(self):
        ingested = await asyncio.gather(*(self.ingest_venue(adapter) for adapter in self.adapters))
        markets = [market for discovered, _ in ingested for market in discovered]
        books = {key: value for _, snapshots in ingested for key, value in snapshots.items()}
        if self.settings.mode == "simulation":
            reviews = simulation_reviews(markets)
        elif self.settings.review_source == "files" and self.settings.reviews_file:
            content = await asyncio.to_thread(self.settings.reviews_file.read_text)
            reviews = TypeAdapter(list[Review]).validate_python(json.loads(content))
        else:
            reviews = []
        definitions = []
        if self.settings.review_source == "files" and self.settings.definitions_file:
            content = await asyncio.to_thread(self.settings.definitions_file.read_text)
            definitions = TypeAdapter(list[ContractDefinition]).validate_json(content)
        if len({d.market_id for d in definitions}) != len(definitions):
            raise ValueError("Duplicate contract definitions for a market")
        supplied = {d.market_id: d for d in definitions}
        # Manual definitions replace the entire draft, including stale definitions.
        # Never silently fill missing reviewed fields from an automatic interpretation.
        definitions = [
            supplied[market.id] if market.id in supplied else extract_contract(market).definition
            for market in markets
        ]
        with self.tracing.span("matching", market_count=len(markets)):
            matches = (
                await self.review_provider.matches(self.settings.mode, markets)
                if self.settings.mode == "live" and self.settings.review_source == "database"
                else match_markets(markets, reviews, definitions)
            )
        indexed = {market.id: market for market in markets}
        now = utcnow()

        # Calculation work must not block the event loop as the monitored set grows.
        def calculate():
            with self.tracing.span("evaluation", match_count=len(matches)):
                return [
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

        evaluations = await asyncio.to_thread(calculate)
        with self.tracing.span("publication", evaluation_count=len(evaluations)):
            published = await self.repository.publish(self.settings.mode, matches, evaluations)
        return {
            "mode": self.settings.mode,
            "markets": len(markets),
            "books": len(books),
            "matches": len(matches),
            "opportunities": published,
        }
