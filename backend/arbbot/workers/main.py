import argparse
import asyncio
import json
import logging
import signal
from contextlib import AsyncExitStack

import httpx
from sqlalchemy import text

from arbbot.config import Settings
from arbbot.discovery.service import CatalogService
from arbbot.exchanges.recorded import RecordedAdapter, RecordedExchange
from arbbot.ingestion.pipeline import Pipeline, safe_error
from arbbot.observability.tracing import correlation_fields, create_tracing
from arbbot.sources.fetch import SourceFetcher
from arbbot.storage.database import Database
from arbbot.storage.repository import Repository
from arbbot.venues import build_adapters


class JSONFormatter(logging.Formatter):
    def format(self, record):
        fields = {"level": record.levelname, "message": record.getMessage(), "logger": record.name}
        fields.update(correlation_fields())
        for key in ("venue", "status", "error", "market_count", "book_count"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields)


async def run(once=False):
    settings = Settings()
    db = Database(settings)
    repository = Repository(db)
    tracing = create_tracing(settings, "arbbot-worker")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        async with db.engine.connect() as lock_connection:
            if db.engine.dialect.name == "postgresql":
                locked = await lock_connection.scalar(text("SELECT pg_try_advisory_lock(71920413)"))
                await lock_connection.commit()
                if not locked:
                    raise RuntimeError("Another ingestion worker holds the database lock")
            try:
                recording = (
                    RecordedExchange(settings.recording_file) if settings.recording_file else None
                )
                async with (
                    AsyncExitStack() as resources,
                    httpx.AsyncClient(
                        timeout=httpx.Timeout(15),
                        follow_redirects=False,
                        transport=recording.transport if recording else None,
                    ) as client,
                ):
                    adapters = build_adapters(client, settings, once)
                    if recording:
                        adapters = [RecordedAdapter(adapter) for adapter in adapters]
                    source_fetcher = SourceFetcher(
                        transport=recording.transport if recording else None,
                        ttl=0 if recording else 300,
                    )
                    for adapter in adapters:
                        if hasattr(adapter, "aclose"):
                            resources.push_async_callback(adapter.aclose)
                    catalog = None
                    if settings.mode == "live":
                        catalog = CatalogService(
                            settings, repository, adapters, source_fetcher=source_fetcher
                        )
                        resources.push_async_callback(catalog.aclose)
                        if once:
                            await asyncio.gather(
                                *(catalog.refresh(adapter) for adapter in adapters)
                            )
                        else:
                            await catalog.restore()
                            catalog.start()
                    pipeline = Pipeline(
                        settings,
                        repository,
                        adapters,
                        tracing=tracing,
                        catalog=catalog,
                        source_fetcher=source_fetcher,
                    )
                    if catalog is not None and not once:
                        await pipeline.run(stop)
                    while (catalog is None or once) and not stop.is_set():
                        try:
                            result = await pipeline.cycle()
                            print(json.dumps(result), flush=True)
                        except Exception as exc:
                            for venue in settings.enabled_venues:
                                await repository.set_health(
                                    settings.mode, venue, "degraded", error=safe_error(exc)
                                )
                            if once:
                                raise
                            logging.getLogger(__name__).error(
                                "cycle_failed", extra={"error": safe_error(exc)}
                            )
                        if once:
                            break
                        try:
                            await asyncio.wait_for(stop.wait(), timeout=settings.poll_seconds)
                        except TimeoutError:
                            pass
            finally:
                if db.engine.dialect.name == "postgresql":
                    await lock_connection.execute(text("SELECT pg_advisory_unlock(71920413)"))
                    await lock_connection.commit()
    finally:
        try:
            await db.close()
        finally:
            await asyncio.to_thread(tracing.shutdown)


def main():
    parser = argparse.ArgumentParser(description="Continuously discover and evaluate markets")
    parser.add_argument(
        "--once", action="store_true", help="Ingest and evaluate one complete cycle"
    )
    args = parser.parse_args()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.once))


if __name__ == "__main__":
    main()
