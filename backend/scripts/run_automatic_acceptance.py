"""Offline PostgreSQL / real worker / HTTP API acceptance without human seed data."""

import argparse
import asyncio
import json
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from automatic_dataset import create_automatic_recording
from run_acceptance import PYTHON, ROOT, Harness
from sqlalchemy import func, select, text

from arbbot.config import Settings
from arbbot.storage.database import Database
from arbbot.storage.models import DecisionRevisionRecord, DraftRevisionRecord
from arbbot.storage.repository import Repository


class AutomaticHarness(Harness):
    def __init__(self, directory, database_url):
        super().__init__(directory, database_url)
        self.recording = create_automatic_recording(directory)
        self.env["ARBBOT_AUTOMATIC_QUALIFICATION"] = "true"
        self.env["ARBBOT_DISCOVERY_LIMIT"] = "4"
        self.env["ARBBOT_MAX_QUOTE_AGE_SECONDS"] = "20"
        self.settings = Settings(
            _env_file=None,
            database_url=self.url,
            mode="live",
            automatic_qualification=True,
            enabled_venues=("kalshi", "polymarket_us"),
        )

    async def run(self, browser=False):
        admin = Database(Settings(_env_file=None, database_url=self.admin_url))
        async with admin.engine.begin() as connection:
            await connection.execute(text("CREATE SCHEMA " + self.schema))
        await admin.close()
        await asyncio.to_thread(
            subprocess.run,
            [PYTHON, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=self.env,
            check=True,
        )
        self.db = Database(self.settings)
        self.start(
            "api",
            [
                PYTHON,
                "-m",
                "uvicorn",
                "arbbot.api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.api_port),
            ],
            ROOT,
        )
        self.start("worker", [PYTHON, "-m", "arbbot.workers.main"], ROOT)
        async with httpx.AsyncClient(base_url=self.env["BACKEND_URL"], timeout=15) as api:
            self.api = api

            async def ready():
                try:
                    return (await api.get("/health/ready")).status_code == 200
                except httpx.TransportError:
                    return False

            await self.wait("API and additive migrations ready", ready)

            async def qualified():
                rows = (await api.get("/api/v1/opportunities")).json()
                self.last_positive = rows
                return bool(
                    rows
                    and all(
                        r["review"] is None and r["qualification"]["status"] == "qualified"
                        for r in rows
                    )
                )

            await self.wait("Automatic qualified estimates without review/account setup", qualified)
            assert (await api.get("/api/v1/access-summary")).json()["status"] == "unknown"
            async with self.db.sessions() as session:
                for model in (DraftRevisionRecord, DecisionRevisionRecord):
                    assert await session.scalar(select(func.count()).select_from(model)) == 0
            self.results.append("Zero human drafts and decision revisions")
            pair = self.last_positive[0]["match_id"]
            assessment = self.last_positive[0]["qualification"]["assessment_id"]

            async def potential():
                rows = (await api.get("/api/v1/potential-opportunities")).json()
                return bool(rows and all(r["qualification"]["status"] != "qualified" for r in rows))

            await self.wait("Incomplete settlement remains separate potential price gap", potential)
            page = (
                await api.get("/api/v1/matches", params={"qualification": "qualified", "limit": 1})
            ).json()
            assert len(page) == 1 and page[0]["qualification"]["status"] == "qualified"
            self.results.append("Qualification filtering precedes pagination")
            old_book = (await Repository(self.db).latest_books("live"))["kalshi:SYN-1"].id
            self.state(fee_failure=True)

            async def fees_unavailable():
                from arbbot.execution.repository import ExecutionRepository

                async with self.db.sessions() as session:
                    values = [
                        await ExecutionRepository(self.db).current(session, key)
                        for key in ("live:fees:kalshi:SYN-1", "live:fees:polymarket_us:synthetic-1")
                    ]
                return all(
                    value and value.value.kind == "fee_unavailable" for value in values
                ) and (await self.no_positive())

            await self.wait("Fee outage withdraws qualified estimates", fees_unavailable)
            new_book = (await Repository(self.db).latest_books("live"))["kalshi:SYN-1"].id
            assert new_book != old_book
            self.results.append("Book polling continues during public fee outage")
            self.state(fee_failure=False)
            await self.wait("Public fee provider recovers automatically", qualified)
            self.state(source_changed="https://assets.kalshi.com/automatic/spec-1.txt")

            async def source_invalid():
                summary = (await api.get(f"/api/v1/matches/{pair}/qualification")).json()
                return summary["status"] != "qualified" and await self.no_positive()

            await self.wait("Source amendment invalidates qualification", source_invalid)
            summary = (await api.get(f"/api/v1/matches/{pair}/qualification")).json()
            assert summary["status"] != "qualified"
            history = (
                await api.get(
                    f"/api/v1/matches/{pair}/qualification", params={"assessment_id": assessment}
                )
            ).json()
            assert history["status"] == "stale"
            self.state(source_changed=None)
            await self.wait("Restored supported sources requalify without human action", qualified)
            await self.stop("worker")
            self.start("worker", [PYTHON, "-m", "arbbot.workers.main"], ROOT)
            await self.wait("Persistent worker restart retains automatic workflow", qualified)
            report = {
                "results": self.results,
                "feed_origin": "synthetic_recording",
                "human_review_records": 0,
                "account_profile": "unknown",
                "scope": "Backend/API only; no browser workflow added",
                "authentic_recordings": (
                    "Preserved; missing settlement applicability remains incomplete"
                ),
                "completed_at_epoch": time.time(),
            }
            (self.directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    async def no_positive(self):
        return (await self.api.get("/api/v1/opportunities")).json() == []


async def main(args):
    directory = args.output or Path(tempfile.mkdtemp(prefix="arbbot-auto-acceptance-"))
    directory.mkdir(parents=True, exist_ok=True)
    harness = AutomaticHarness(directory, args.database_url)
    try:
        await harness.run()
        print(json.dumps({"acceptance": "passed", "artifacts": str(directory)}))
    except Exception:
        await harness.diagnostics()
        raise
    finally:
        await harness.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--database-url", default="postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot"
    )
    asyncio.run(main(parser.parse_args()))
