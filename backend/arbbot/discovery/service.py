"""Refresh catalog/evidence in background tasks while quotes use an immutable snapshot."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from arbbot.discovery.inventory import CatalogInventory
from arbbot.discovery.models import CatalogReport
from arbbot.domain import utcnow
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

    def start(self):
        if self.tasks:
            raise RuntimeError("Catalog scheduler already started")
        self.tasks = [
            asyncio.create_task(self._run(adapter), name=f"catalog-{adapter.venue}")
            for adapter in self.adapters
        ]

    async def aclose(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def _run(self, adapter):
        while True:
            try:
                await self.refresh(adapter)
            except Exception as exc:
                # A failed database write cannot kill the scheduler permanently.
                logger.warning(
                    "catalog_refresh_failed",
                    extra={"venue": adapter.venue, "error": type(exc).__name__},
                )
            await asyncio.sleep(self.settings.catalog_refresh_seconds)

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
        slots = max(0, self.settings.discovery_limit - len(preferred))
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
        return preferred[: self.settings.discovery_limit] + rotated[:slots]

    async def refresh(self, adapter):
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

                async def enrich(market):
                    async with self.enrichment_slots:
                        await self.repository.save_market(market)
                        result = await adapter.enrich_sources(market, self.sources, self.fetcher)
                        await self.repository.save_market(result)
                        return result

                async with asyncio.TaskGroup() as group:
                    pending = [group.create_task(enrich(market)) for market in selected]
                markets = [task.result() for task in pending]
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
            monitoring_limit=self.settings.discovery_limit,
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
