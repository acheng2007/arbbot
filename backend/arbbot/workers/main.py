import argparse
import asyncio
import json
import logging
import signal

import httpx
from sqlalchemy import text

from arbbot.config import Settings
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.pipeline import Pipeline, safe_error
from arbbot.storage.database import Database
from arbbot.storage.repository import Repository


class JSONFormatter(logging.Formatter):
    def format(self, record):
        fields = {"level": record.levelname, "message": record.getMessage(), "logger": record.name}
        for key in ("venue", "status", "error", "market_count", "book_count"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields)


async def run(once=False):
    settings = Settings()
    db = Database(settings)
    repository = Repository(db)
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
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(15), follow_redirects=False
                ) as client:
                    if settings.mode == "simulation":
                        adapters = [SimulationAdapter(venue) for venue in ("kalshi", "polymarket")]
                    else:
                        adapters = [
                            KalshiAdapter(ExchangeHTTP(client), settings),
                            PolymarketAdapter(ExchangeHTTP(client), settings.polymarket_market_ids),
                        ]
                    pipeline = Pipeline(settings, repository, adapters)
                    while not stop.is_set():
                        try:
                            result = await pipeline.cycle()
                            print(json.dumps(result), flush=True)
                        except Exception as exc:
                            for venue in ("kalshi", "polymarket"):
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
        await db.close()


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
