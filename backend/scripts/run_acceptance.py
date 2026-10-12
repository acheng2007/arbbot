"""Isolated PostgreSQL, persistent recorded worker, FastAPI and Next.js acceptance."""

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
from acceptance_dataset import create_recording
from acceptance_seed import ACTOR, seed
from sqlalchemy import text

from arbbot.config import Settings
from arbbot.domain import utcnow
from arbbot.execution.models import ConfigurationWrite
from arbbot.execution.repository import ExecutionRepository
from arbbot.reviews.models import DecisionWrite
from arbbot.reviews.repository import ReviewRepository
from arbbot.storage.database import Database

ROOT = Path(__file__).resolve().parents[2]
PYTHON = str(ROOT / ".venv/bin/python")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Harness:
    def __init__(self, directory, database_url):
        self.directory, self.admin_url = directory, database_url
        self.schema = "arbbot_acceptance_" + uuid4().hex
        self.url = database_url + "?options=-csearch_path%3D" + self.schema
        self.api_port, self.web_port = free_port(), free_port()
        self.recording = create_recording(directory)
        self.control = directory / "control.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ARBBOT_")}
        self.env.update(
            ARBBOT_DATABASE_URL=self.url,
            ARBBOT_MODE="live",
            ARBBOT_RECORDING_FILE=str(self.recording),
            ARBBOT_ENABLED_VENUES='["kalshi","polymarket_us"]',
            ARBBOT_DISCOVERY_MODE="broad",
            ARBBOT_DISCOVERY_LIMIT="2",
            ARBBOT_POLL_SECONDS="1",
            ARBBOT_FEE_REFRESH_SECONDS="10",
            ARBBOT_CATALOG_REFRESH_SECONDS="10",
            ARBBOT_CATALOG_TIMEOUT_SECONDS="20",
            ARBBOT_CATALOG_MAX_AGE_SECONDS="120",
            ARBBOT_MAX_QUOTE_AGE_SECONDS="8",
            ARBBOT_MAX_CONTRACTS="10",
            ARBBOT_POLYMARKET_WEBSOCKET="false",
            ARBBOT_SSE_SECONDS="0.5",
            BACKEND_URL=f"http://127.0.0.1:{self.api_port}",
            ARBBOT_WEB_DATA_SOURCE="recorded_backend",
        )
        self.processes, self.logs = {}, []
        self.results = []
        self.settings = Settings(
            _env_file=None,
            **{
                key.removeprefix("ARBBOT_").lower(): json.loads(value)
                if key == "ARBBOT_ENABLED_VENUES"
                else value
                for key, value in self.env.items()
                if key.startswith("ARBBOT_")
            },
        )

    def start(self, name, command, cwd):
        log = (self.directory / f"{name}.log").open("a")
        self.logs.append(log)
        self.processes[name] = subprocess.Popen(
            command,
            cwd=cwd,
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    async def stop(self, name):
        process = self.processes.pop(name, None)
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.to_thread(process.wait, 15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                await asyncio.to_thread(process.wait, 5)

    def state(self, **changes):
        state = json.loads(self.control.read_text())
        state.update(changes, epoch=state["epoch"] + 1)
        pending = self.control.with_suffix(".tmp")
        pending.write_text(json.dumps(state))
        pending.replace(self.control)
        return state

    async def wait(self, label, predicate, deadline_seconds=60):
        deadline = time.monotonic() + deadline_seconds
        while time.monotonic() < deadline:
            if await predicate():
                self.results.append(label)
                print(label, flush=True)
                return
            failed = [
                name for name, process in self.processes.items() if process.poll() is not None
            ]
            if failed:
                raise RuntimeError(f"Acceptance services exited: {failed}; see {self.directory}")
            await asyncio.sleep(0.25)
        raise AssertionError(f"Acceptance timed out: {label}; logs at {self.directory}")

    async def run(self, browser=True):
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
        self.seeded = await seed(self.settings, self.db)
        self.configuration, self.reviews = ExecutionRepository(self.db), ReviewRepository(self.db)
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
        async with httpx.AsyncClient(base_url=self.env["BACKEND_URL"], timeout=10) as api:
            self.api = api

            async def ready():
                try:
                    return (await api.get("/health/ready")).status_code == 200
                except httpx.TransportError:
                    return False

            await self.wait("API and migrations ready", ready)

            async def statuses():
                rows = (await api.get("/api/v1/evaluations", params={"limit": 200})).json()
                by_pair = {row["match_id"]: row["status"] for row in rows}
                current = (
                    await api.get("/api/v1/matches", params={"status": "verified", "limit": 20})
                ).json()
                wanted = {1: "profitable", 2: "unprofitable", 3: "blocked", 4: "invalid"}
                return all(
                    any(
                        m["left_id"] == f"kalshi:SYN-{i}" and by_pair.get(m["id"]) == status
                        for m in current
                    )
                    for i, status in wanted.items()
                )

            await self.wait(
                "Four reviewed pairs: profitable, unprofitable, blocked, invalid", statuses
            )
            self.matches = {
                int(m["left_id"].rsplit("-", 1)[1]): m
                for m in (
                    await api.get("/api/v1/matches", params={"status": "verified", "limit": 20})
                ).json()
            }
            await self.wait("Eligible positive estimate is publicly readable", self.positive)
            opportunities = self.last_positive
            assert len(opportunities) == 1 and opportunities[0]["classification"] == "simulation"
            assert opportunities[0]["legs"][1]["native_action"] == "short_instrument"
            assert opportunities[0]["fee_revision_ids"] and opportunities[0]["access_revision_id"]
            assert (await api.get("/api/v1/access-summary")).json()["status"] == "verified"
            summaries = (await api.get("/api/v1/market-summaries", params={"limit": 200})).json()
            assert len(summaries) == 200 and all("rules" not in m for m in summaries)
            target = (
                await api.get(
                    "/api/v1/market-summaries",
                    params={
                        "q": "synthetic-3-counterpart-204",
                        "category": "acceptance",
                        "status": "open",
                    },
                )
            ).json()
            assert len(target) == 1
            counterparts = (
                await api.get(
                    "/api/v1/matches",
                    params={"market_id": "kalshi:SYN-3", "limit": 200, "offset": 200},
                )
            ).json()
            assert counterparts
            assert (await api.get("/api/v1/markets/" + target[0]["id"])).json()["rules"]
            authentic = (
                await api.get("/api/v1/matches", params={"market_id": "kalshi:KXMLB-26-LAD"})
            ).json()
            assert authentic and all(m["status"] != "verified" for m in authentic)
            self.results.append(
                "Catalog pagination, >200 counterparts, exact lookup, authentic pair unapproved"
            )
            # Read the real FastAPI stream and assert publication reached its snapshot payload.
            async with api.stream("GET", "/api/v1/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        if json.loads(line[6:])["opportunities"]:
                            self.results.append("Published estimate delivered through FastAPI SSE")
                            break
            self.state(phase="publication_move")

            async def recheck_lost():
                result = (
                    await api.get("/api/v1/evaluations", params={"match_id": self.matches[1]["id"]})
                ).json()
                return (
                    result
                    and result[0]["status"] == "unprofitable"
                    and not await self.opportunities()
                )

            await self.wait(
                "Publication recheck price movement eliminates preliminary profit", recheck_lost
            )
            self.state(phase="baseline")
            await self.wait("Quotes recover with a newly calculated estimate", self.positive)
            self.state(fee_failure=True)

            async def fee_unavailable():
                result = (
                    await api.get("/api/v1/evaluations", params={"match_id": self.matches[1]["id"]})
                ).json()
                return (
                    result
                    and any("fee_policy_unavailable" in r for r in result[0]["blocked_reasons"])
                    and not await self.opportunities()
                )

            await self.wait(
                "Fee-provider outage publishes unavailable policies and withdraws", fee_unavailable
            )
            self.state(fee_failure=False)
            await self.wait(
                "Fee-provider recovery retrieves fresh immutable policies", self.positive
            )
            await self.withdrawals()
            await self.wait("Fresh estimate before worker restart", self.positive)
            before = self.last_positive[0]
            await self.stop("worker")

            async def expired():
                return not await self.opportunities()

            await self.wait(
                "Quote expiry withdraws while worker is stopped", expired, deadline_seconds=20
            )
            self.start("worker", [PYTHON, "-m", "arbbot.workers.main"], ROOT)
            await self.wait(
                "Worker restart resumes persisted catalog and monitoring", self.positive
            )
            after = self.last_positive[0]
            assert after["id"] != before["id"] and after["evaluated_at"] > before["evaluated_at"]
            self.state(outage=["polymarket_us"])
            await self.wait("Venue outage withdraws affected estimates", expired)
            self.state(outage=[])
            await self.wait(
                "Venue recovery recalculates rather than replaying old estimates", self.positive
            )
            assert self.last_positive[0]["id"] != after["id"]
            journal = [
                json.loads(line)
                for line in (self.directory / "requests.jsonl").read_text().splitlines()
            ]
            for venue in ("kalshi", "polymarket_us"):
                urls = {
                    row["url"] for row in journal if row["venue"] == venue and row["kind"] == "book"
                }
                assert len(urls) >= 3
            self.results.append("Pair-aware budget rotation monitors multiple books on both venues")
            if browser:
                self.start(
                    "web",
                    [
                        "npm",
                        "run",
                        "dev",
                        "--",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        str(self.web_port),
                    ],
                    ROOT / "apps/web",
                )

                async def web_ready():
                    try:
                        async with httpx.AsyncClient() as web:
                            return (
                                await web.get(f"http://127.0.0.1:{self.web_port}/opportunities")
                            ).status_code == 200
                    except httpx.TransportError:
                        return False

                await self.wait("Next.js connected to recorded PostgreSQL backend", web_ready)
                browser_env = {
                    **self.env,
                    "ARBBOT_ACCEPTANCE_WEB_URL": f"http://127.0.0.1:{self.web_port}",
                    "ARBBOT_ACCEPTANCE_CONTROL": str(self.control),
                    "ARBBOT_ACCEPTANCE_OUTPUT": str(self.directory),
                }
                await asyncio.to_thread(
                    subprocess.run,
                    ["npm", "run", "test:acceptance"],
                    cwd=ROOT / "apps/web",
                    env=browser_env,
                    check=True,
                )
                self.results.append("Desktop/mobile browser workflow and SSE recovery")
        (self.directory / "results.json").write_text(
            json.dumps({"schema": self.schema, "checks": self.results}, indent=2) + "\n"
        )

    async def opportunities(self):
        response = await self.api.get("/api/v1/opportunities")
        response.raise_for_status()
        return response.json()

    async def positive(self):
        rows = await self.opportunities()
        if rows:
            self.last_positive = rows
        return bool(rows)

    async def withdrawals(self):
        async def absent():
            return not await self.opportunities()

        current = self.seeded["access"]
        restricted = await self.configuration.save(
            "live",
            ConfigurationWrite(
                expected_revision_id=current.id,
                value=current.value.model_copy(update={"status": "restricted"}),
                reason="Synthetic access withdrawal",
            ),
            ACTOR,
        )
        assert not await self.opportunities()
        await self.configuration.save(
            "live",
            ConfigurationWrite(
                expected_revision_id=restricted.id,
                value=current.value,
                reason="Restore synthetic reviewed access",
            ),
            ACTOR,
        )
        await self.wait("Access revision withdrawal and renewed evaluation", self.positive)
        decision = self.seeded["decisions"][1]
        revoked = await self.reviews.save_decision(
            "live",
            DecisionWrite(
                expected_revision_id=decision.id,
                left_draft_id=decision.left_draft_id,
                right_draft_id=decision.right_draft_id,
                action="revoked",
                reason="Synthetic review withdrawal",
            ),
            ACTOR,
        )
        assert not await self.opportunities()
        await self.reviews.save_decision(
            "live",
            DecisionWrite(
                expected_revision_id=revoked.id,
                left_draft_id=decision.left_draft_id,
                right_draft_id=decision.right_draft_id,
                action="verified",
                review=decision.review,
                reason="Renew synthetic settlement approval",
            ),
            ACTOR,
        )
        await self.wait("Review revision withdrawal and renewed evaluation", self.positive)
        async with self.db.sessions() as session:
            fee = await self.configuration.current(session, "live:fees:kalshi:SYN-1")
        from datetime import timedelta

        expired_fee = await self.configuration.save(
            "live",
            ConfigurationWrite(
                expected_revision_id=fee.id,
                value=fee.value.model_copy(update={"expires_at": utcnow() + timedelta(seconds=1)}),
                reason="Synthetic fee-policy expiry",
            ),
            ACTOR,
        )
        await self.wait("Fee-policy expiry withdraws estimate", absent)
        await self.configuration.save(
            "live",
            ConfigurationWrite(
                expected_revision_id=expired_fee.id,
                value=fee.value,
                reason="Restore documented synthetic instrument policy",
            ),
            ACTOR,
        )
        await self.wait("Fee-policy renewal recalculates estimate", self.positive)

        from acceptance_dataset import definition

        from arbbot.reviews.models import DraftWrite
        from arbbot.sources.models import SourceCapture
        from arbbot.sources.repository import SourceRepository
        from arbbot.storage.repository import Repository

        source_store = SourceRepository(self.db)
        draft = await self.reviews.current_draft("live", "kalshi:SYN-1")
        source = await source_store.get("live", draft.source_artifact_ids[0])
        capture = SourceCapture(
            mode="live",
            venue=source.venue,
            market_id=source.market_id,
            url=source.url,
            label=source.label,
            content_type=source.content_type,
            content=source.content,
            retrieved_at=utcnow(),
        )
        await source_store.record(
            capture.model_copy(
                update={"content": capture.content + b"\nSYNTHETIC source-change test.\n"}
            )
        )
        assert not await self.opportunities()
        await source_store.record(capture.model_copy(update={"retrieved_at": utcnow()}))
        assert not await self.opportunities(), "Restored bytes replayed an old approval"
        refreshed = []
        for market_id in ("kalshi:SYN-1", "polymarket_us:synthetic-1"):
            current_draft = await self.reviews.current_draft("live", market_id)
            market = await Repository(self.db).market("live", market_id)
            refreshed.append(
                await self.reviews.save_draft(
                    "live",
                    market_id,
                    DraftWrite(
                        expected_revision_id=current_draft.id,
                        definition=definition(market, 1),
                        source_artifact_ids=current_draft.source_artifact_ids,
                        reason="Re-review restored synthetic source revision",
                    ),
                    ACTOR,
                )
            )
        current = await self.reviews.current_decision(
            "live", refreshed[0].market.id, refreshed[1].market.id
        )
        review = current.revision.review.model_copy(
            update={
                "left_terms_hash": refreshed[0].market.terms_hash,
                "right_terms_hash": refreshed[1].market.terms_hash,
                "left_definition_hash": refreshed[0].definition_hash,
                "right_definition_hash": refreshed[1].definition_hash,
            }
        )
        await self.reviews.save_decision(
            "live",
            DecisionWrite(
                expected_revision_id=current.revision.id,
                left_draft_id=refreshed[0].id,
                right_draft_id=refreshed[1].id,
                action="verified",
                review=review,
                reason="Renew approval after synthetic source review",
            ),
            ACTOR,
        )
        await self.wait(
            "Source revision withdrawal cannot replay old approval; renewed review recovers",
            self.positive,
        )

    async def close(self):
        for name in list(self.processes):
            await self.stop(name)
        for log in self.logs:
            log.close()
        if hasattr(self, "db"):
            await self.db.close()


async def main(args):
    directory = args.output or Path(tempfile.mkdtemp(prefix="arbbot-acceptance-"))
    harness = Harness(directory, args.database_url)
    try:
        await harness.run(browser=not args.no_browser)
        print(json.dumps({"acceptance": "passed", "artifacts": str(directory)}), flush=True)
    finally:
        await harness.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default="postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    asyncio.run(main(parser.parse_args()))
