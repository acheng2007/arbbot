"""Refresh catalog/evidence in background tasks while quotes use an immutable snapshot."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from arbbot.discovery.inventory import CatalogInventory
from arbbot.discovery.models import CatalogReport
from arbbot.domain import digest, utcnow
from arbbot.exchanges.discovery import scan_catalog
from arbbot.sources.fetch import SourceFetcher
from arbbot.sources.repository import SourceRepository
from arbbot.storage.models import CatalogRecord

logger = logging.getLogger(__name__)


class CatalogUnavailable(Exception):
    pass


class CatalogService:
    def __init__(self, settings, repository, adapters, *, source_fetcher=None):
        self.settings, self.repository, self.adapters = settings, repository, adapters
        self.sources = SourceRepository(repository.database, settings.source_max_bytes)
        self.fetcher = source_fetcher or SourceFetcher(max_bytes=settings.source_max_bytes)
        self.snapshots = {}
        self.catalogs = {}
        self.inventory = CatalogInventory(settings, repository)
        self.tasks = []
        self.enrichment_slots = asyncio.Semaphore(8)
        self.pending_enrichment = {}
        self.enrichment_ready = asyncio.Event()
        self.changed = asyncio.Event()

    def start(self):
        if self.tasks:
            raise RuntimeError("Catalog scheduler already started")
        self.tasks = [
            asyncio.create_task(self._run(adapter), name=f"catalog-{adapter.venue}")
            for adapter in self.adapters
        ] + [asyncio.create_task(self._enrich(), name="source-enrichment")]

    async def aclose(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def _run(self, adapter):
        while True:
            try:
                await self.refresh(adapter, enrich=False)
            except Exception as exc:
                # A failed database write cannot kill the scheduler permanently.
                logger.warning(
                    "catalog_refresh_failed",
                    extra={"venue": adapter.venue, "error": type(exc).__name__},
                )
            await asyncio.sleep(self.settings.catalog_refresh_seconds)

    def scope(self, adapter):
        watchlist = list(getattr(adapter, "tickers", getattr(adapter, "market_ids", ())))
        return digest(
            {
                "mode": self.settings.discovery_mode,
                "watchlist": watchlist if self.settings.discovery_mode == "focused" else [],
                "families": [f.model_dump(mode="json") for f in self.settings.discovery_families]
                if self.settings.discovery_mode == "focused" and not watchlist
                else [],
                "page_size": self.settings.catalog_page_size,
            }
        )

    async def restore(self):
        """Recover still-fresh persisted catalog before starting network refreshes."""
        reports = await catalog_reports(self.repository.database, self.settings.mode)
        for report in reports:
            adapter = next((a for a in self.adapters if a.venue == report.venue), None)
            if (
                report.valid_until <= utcnow()
                or adapter is None
                or report.query_scope != self.scope(adapter)
            ):
                continue
            if self.settings.discovery_mode == "broad":
                markets = await self.inventory.markets(report.venue)
            else:
                restored = await asyncio.gather(
                    *(
                        self.repository.market(self.settings.mode, mid)
                        for mid in report.selected_market_ids
                    )
                )
                markets = [market for market in restored if market is not None]
            if markets:
                self.catalogs[report.venue] = (report.valid_until, tuple(markets))
                selected = set(report.selected_market_ids)
                self.snapshots[report.venue] = (
                    report.valid_until,
                    tuple(m for m in markets if m.id in selected),
                )

    async def _enrich(self):
        while True:
            await self.enrichment_ready.wait()
            pending, self.pending_enrichment = self.pending_enrichment, {}
            self.enrichment_ready.clear()
            for adapter, markets in pending.values():

                async def enrich_one(market, adapter=adapter):
                    async with self.enrichment_slots:
                        try:
                            base = adapter.normalize_market(market.raw)
                            result = await adapter.enrich_sources(base, self.sources, self.fetcher)
                            result = result.model_copy(
                                update={
                                    "settlement_details": {
                                        **result.settlement_details,
                                        "catalog_input_hash": base.terms_hash,
                                    }
                                }
                            )
                            previous = await self.repository.market(result.mode, result.id)
                            if (
                                previous
                                and previous.settlement_details.get("applicability_base_hash")
                                == result.terms_hash
                            ):
                                result = result.model_copy(
                                    update={"settlement_details": previous.settlement_details}
                                )
                            await self.repository.save_market(result)
                            self.changed.set()
                        except Exception as exc:
                            logger.warning(
                                "source_enrichment_failed",
                                extra={"venue": adapter.venue, "error": type(exc).__name__},
                            )

                await asyncio.gather(*(enrich_one(market) for market in markets))

    def current(self, venue):
        snapshot = self.snapshots.get(venue)
        if snapshot is None or snapshot[0] <= utcnow():
            raise CatalogUnavailable("Catalog is not ready or has expired")
        return list(snapshot[1])

    def all_current(self, venue):
        snapshot = self.catalogs.get(venue)
        if snapshot is None or snapshot[0] <= utcnow():
            return []
        return list(snapshot[1])

    async def monitored(self, adapter, markets):
        from arbbot.storage.models import MatchRecord

        priority = set(adapter.tickers if adapter.venue == "kalshi" else adapter.market_ids)
        async with self.repository.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(MatchRecord).where(
                        MatchRecord.mode == self.settings.mode,
                        MatchRecord.current.is_(True),
                        MatchRecord.payload["status"].as_string() == "verified",
                    )
                )
            ).all()
        approved = {row.payload[key] for row in rows for key in ("left_id", "right_id")}
        preferred = [m for m in markets if m.external_id in priority or m.id in approved]
        remaining = [m for m in markets if m not in preferred]
        progress = await self.inventory.progress(adapter.venue)
        offset = progress.get("monitoring_offset", 0) % max(1, len(remaining))
        rotated = remaining[offset:] + remaining[:offset]
        slots = max(0, self.settings.monitoring_limit(adapter.venue) - len(preferred))
        progress["monitoring_offset"] = offset + slots
        from arbbot.storage.models import DiscoveryProgressRecord

        async with self.repository.database.sessions.begin() as session:
            await session.merge(
                DiscoveryProgressRecord(
                    key=f"{self.settings.mode}:{adapter.venue}",
                    mode=self.settings.mode,
                    venue=adapter.venue,
                    payload=progress,
                )
            )
        return preferred[: self.settings.monitoring_limit(adapter.venue)] + rotated[:slots]

    async def source_cohort(self, adapter, markets):
        """Durable category rotation independent of the book-monitoring allocation."""
        from collections import defaultdict
        from itertools import zip_longest

        from arbbot.storage.models import DiscoveryProgressRecord

        groups = defaultdict(list)
        for market in sorted(markets, key=lambda m: m.id):
            groups[market.category_group].append(market)
        ordered = [
            m
            for row in zip_longest(*(groups[k] for k in sorted(groups)))
            for m in row
            if m is not None
        ]
        key = f"{self.settings.mode}:{adapter.venue}:source-rotation"
        async with self.repository.database.sessions.begin() as session:
            previous = await session.get(DiscoveryProgressRecord, key, with_for_update=True)
            offset = (previous.payload.get("offset", 0) if previous else 0) % max(1, len(ordered))
            selected = (ordered[offset:] + ordered[:offset])[:64]
            await session.merge(
                DiscoveryProgressRecord(
                    key=key,
                    mode=self.settings.mode,
                    venue=adapter.venue,
                    payload={"offset": offset + len(selected)},
                )
            )
        return selected

    async def refresh(self, adapter, *, enrich=True):
        started = utcnow()
        scan = None
        error = None
        markets = []
        catalog_markets = []
        progress = {}
        broad = self.settings.discovery_mode == "broad" and adapter.venue in {
            "kalshi",
            "polymarket_us",
        }
        try:
            async with asyncio.timeout(self.settings.catalog_timeout_seconds):
                scan = (
                    await self.inventory.scan(adapter)
                    if broad
                    else await scan_catalog(
                        adapter,
                        self.settings.discovery_families,
                        self.settings.discovery_limit,
                        self.settings.discovery_scan_pages,
                    )
                )
                catalog_markets = list(scan.markets)
                selected = (
                    await self.monitored(adapter, catalog_markets) if broad else catalog_markets
                )
                if broad:
                    progress = await self.inventory.progress(adapter.venue)

                async def enrich_market(market):
                    async with self.enrichment_slots:
                        await self.repository.save_market(market, from_catalog=True)
                        result = await adapter.enrich_sources(market, self.sources, self.fetcher)
                        await self.repository.save_market(result)
                        return result

                if not broad:
                    for market in selected:
                        await self.repository.save_market(market, from_catalog=True)
                if enrich:
                    async with asyncio.TaskGroup() as group:
                        pending = [group.create_task(enrich_market(market)) for market in selected]
                    markets = [task.result() for task in pending]
                else:
                    # At most one bounded cohort per venue; newer work replaces missed ticks.
                    markets = selected
                    source_markets = await self.source_cohort(adapter, catalog_markets)
                    self.pending_enrichment[adapter.venue] = (adapter, tuple(source_markets))
                    self.enrichment_ready.set()
                # Family scans do not call the adapter's general-discovery method.
                if hasattr(adapter, "stream"):
                    await adapter.stream.subscribe(markets)
        except Exception as exc:
            error = type(exc).__name__
            if broad:
                progress = await self.inventory.progress(adapter.venue)
        completed = utcnow()
        valid_until = started + timedelta(seconds=self.settings.catalog_max_age_seconds)
        if error and adapter.venue in self.snapshots:
            valid_until, previous = self.snapshots[adapter.venue]
            markets = list(previous)
        missing = tuple(
            m.id for m in markets if m.settlement_details.get("source_status") != "captured"
        )
        report = CatalogReport(
            mode=self.settings.mode,
            discovery_mode=self.settings.discovery_mode,
            query_scope=self.scope(adapter),
            venue=adapter.venue,
            status="failed"
            if error
            else "degraded"
            if missing or not markets or (scan and scan.truncated)
            else "ready",
            started_at=started,
            completed_at=completed,
            valid_until=valid_until,
            selected_market_ids=tuple(m.id for m in markets),
            decisions=scan.decisions if scan else (),
            pages_scanned=scan.pages_scanned if scan else 0,
            truncated=scan.truncated if scan else progress.get("continuation") is not None,
            catalog_market_count=len(catalog_markets),
            monitoring_limit=self.settings.monitoring_limit(adapter.venue),
            continuation=progress.get("continuation"),
            coverage_complete=bool(progress.get("coverage_complete"))
            if broad
            else bool(scan and not scan.truncated),
            missing_source_market_ids=missing,
            error=error,
        )
        async with self.repository.database.sessions.begin() as session:
            await session.merge(
                CatalogRecord(
                    key=f"{self.settings.mode}:{adapter.venue}",
                    mode=self.settings.mode,
                    venue=adapter.venue,
                    payload=report.model_dump(mode="json"),
                )
            )
        if not error:
            self.snapshots[adapter.venue] = (valid_until, tuple(markets))
            enriched = {m.id: m for m in markets}
            self.catalogs[adapter.venue] = (
                valid_until,
                tuple(enriched.get(m.id, m) for m in catalog_markets),
            )
            self.changed.set()
        return report


async def catalog_reports(database, mode):
    async with database.sessions() as session:
        rows = (
            await session.scalars(
                select(CatalogRecord)
                .where(CatalogRecord.mode == mode)
                .order_by(CatalogRecord.venue)
            )
        ).all()
    reports = [CatalogReport.model_validate(row.payload) for row in rows]
    return [
        report.model_copy(update={"status": "stale"}) if report.valid_until <= utcnow() else report
        for report in reports
    ]
