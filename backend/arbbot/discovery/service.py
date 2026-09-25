"""Refresh catalog/evidence in background tasks while quotes use an immutable snapshot."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

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

    async def refresh(self, adapter):
        started = utcnow()
        scan = None
        error = None
        markets = []
        try:
            async with asyncio.timeout(self.settings.catalog_timeout_seconds):
                scan = await scan_catalog(
                    adapter,
                    self.settings.discovery_families,
                    self.settings.discovery_limit,
                    self.settings.discovery_scan_pages,
                )

                async def enrich(market):
                    async with self.enrichment_slots:
                        await self.repository.save_market(market)
                        result = await adapter.enrich_sources(market, self.sources, self.fetcher)
                        await self.repository.save_market(result)
                        return result

                async with asyncio.TaskGroup() as group:
                    pending = [group.create_task(enrich(market)) for market in scan.markets]
                markets = [task.result() for task in pending]
                # Family scans do not call the adapter's general-discovery method.
                if hasattr(adapter, "stream"):
                    await adapter.stream.subscribe(markets)
        except Exception as exc:
            error = type(exc).__name__
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
            truncated=scan.truncated if scan else False,
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
