"""Explicit live public-data smoke/benchmark run. Never fabricate absent provider responses."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from arbbot.config import Settings
from arbbot.domain import utcnow
from arbbot.matching.benchmark import ROOT, load_markets, report
from arbbot.matching.classification_input import build_request
from arbbot.matching.classification_provider import DecisionsProvider, ProviderFailure
from arbbot.storage.database import Database
from arbbot.storage.models import Base
from arbbot.storage.repository import Repository


async def run(output, pairs_file, limit):
    configured = Settings()
    if not configured.openrouter_api_key:
        await asyncio.to_thread(
            output.write_text,
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "OPENROUTER_API_KEY is not configured",
                    "checked_at": utcnow().isoformat(),
                    "requested_model": "typesafe/jev-1.13",
                },
                indent=2,
            )
            + "\n",
        )
        return
    rows = json.loads(await asyncio.to_thread(pairs_file.read_text))["pairs"][:limit]
    responses, errors, inputs = {}, {}, {}
    with tempfile.TemporaryDirectory(prefix="arbbot-jev-smoke-") as directory:
        db = Database(Settings(database_url=f"sqlite+aiosqlite:///{directory}/smoke.db"))
        try:
            async with db.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            repository = Repository(db)
            for row in rows:
                for market in load_markets(row):
                    await repository.save_market(market)
            async with db.sessions() as session:
                for row in rows:
                    markets = load_markets(row)
                    _, request = await build_request(
                        session, "live", [m.id for m in markets], "typesafe/jev-1.13"
                    )
                    inputs[row["id"]] = request
            async with httpx.AsyncClient(follow_redirects=False) as client:
                provider = DecisionsProvider(
                    client, configured.openrouter_api_key.get_secret_value(), 2
                )
                semaphore = asyncio.Semaphore(4)

                async def classify(row):
                    async with semaphore:
                        try:
                            value, attempts = await provider.decide(inputs[row["id"]])
                            responses[row["id"]] = value.model_dump(mode="json")
                        except ProviderFailure as exc:
                            errors[row["id"]] = {"error": exc.code, "attempts": exc.attempts}

                await asyncio.gather(*(classify(row) for row in rows))
        finally:
            await db.close()
    await asyncio.to_thread(
        output.write_text,
        json.dumps(
            {
                "status": "completed",
                "checked_at": utcnow().isoformat(),
                "requested_model": "typesafe/jev-1.13",
                "responses": responses,
                "errors": errors,
                "inputs": inputs,
                "benchmark": report(rows, responses),
            },
            indent=2,
        )
        + "\n",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--pairs", type=Path, default=ROOT / "backend/tests/fixtures/jev/benchmark.json"
    )
    parser.add_argument("--limit", type=int, default=1, choices=range(1, 31))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output path to preserve smoke evidence")
    asyncio.run(run(args.output, args.pairs, args.limit))


if __name__ == "__main__":
    main()
