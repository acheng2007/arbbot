"""Connected discovery acceptance, with synthetic financials and authentic catalog terms.

Model answers here are deliberately scripted fault/visibility tests, not accuracy
measurements. benchmark_discovery.py --live measures actual provider responses.
"""

import argparse
import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from run_acceptance import PYTHON, ROOT
from run_automatic_acceptance import AutomaticHarness

from arbbot.domain import digest
from arbbot.matching.classification_input import build_request


class DiscoveryHarness(AutomaticHarness):
    def __init__(self, directory, database_url, web_directory):
        super().__init__(directory, database_url)
        self.web_directory = web_directory
        self.env["ARBBOT_DISCOVERY_LIMIT"] = "8"
        self.env["ARBBOT_MAX_QUOTE_AGE_SECONDS"] = "30"
        data = json.loads(self.recording.read_text())
        corpus = ROOT / "backend/tests/fixtures/discovery_broad/recorded.json"
        for record in json.loads(corpus.read_text())["markets"]:
            raw, venue = record["payload"], record["venue"]
            identity = raw.get("ticker", raw.get("slug"))
            key = "ticker" if venue == "kalshi" else "slug"
            if not any(r.get(key) == identity for r in data["catalogs"][venue]):
                data["catalogs"][venue].append(raw)
        metadata = corpus.parent / "metadata.json"
        data["responses"].update(json.loads(metadata.read_text()))
        self.recording.write_text(json.dumps(data))

    async def run(self, browser=True):
        # Reuse the complete automatic qualification/outage/restart checks.
        await super().run()
        left, right = "kalshi:CONTROLH-2026-D", "polymarket_us:paccc-usho-midterms-2026-11-03-dem"
        async with self.db.sessions() as session:
            _, request = await build_request(session, "live", (left, right), "typesafe/jev-1.13")
        answers = {}
        for key, question in request["questions"].items():
            choices = question["criteria"]
            if key == "event":
                choice = "same_event"
            elif key == "orientation":
                choice = "aligned"
            elif key.endswith("evidence"):
                choice = next((c for c in choices if c != "none"), "none")
            else:
                choice = "insufficient_evidence"
            answers[key] = {
                "type": "choice",
                "choice": choice,
                "confidence": 0.1,
                "probabilities": {c: 1 if c == choice else 0 for c in choices},
            }
        answers["event"]["probabilities"] = {
            "same_event": 0.4,
            "different_event": 0.3,
            "insufficient_evidence": 0.3,
        }
        decisions = self.directory / "discovery-decisions.json"
        decisions.write_text(
            json.dumps(
                {
                    "format": "scripted-discovery-visibility-v1",
                    "status": 200,
                    "pairs": {
                        "|".join(sorted((left, right))): {
                            "model": "typesafe/jev-1.13-20260917",
                            "answers": answers,
                            "usage": {},
                        }
                    },
                }
            )
        )
        await self.stop("worker")
        await self.stop("api")
        self.env.update(
            ARBBOT_CLASSIFICATION_ENABLED="true",
            ARBBOT_CLASSIFICATION_RECORDING_FILE=str(decisions),
        )
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
        async with httpx.AsyncClient(base_url=self.env["BACKEND_URL"], timeout=30) as api:
            self.api = api
            pair_id = digest(["live", *sorted((left, right))])

            async def visible():
                try:
                    response = await api.get(
                        "/api/v1/matches",
                        params={
                            "classification": "suggested",
                            "relationship": "unverified",
                            "category_group": "politics",
                            "limit": 1,
                        },
                    )
                    rows = response.json()
                    return bool(response.status_code == 200 and rows and rows[0]["id"] == pair_id)
                except (httpx.TransportError, ValueError):
                    return False

            await self.wait(
                "Low-score authentic political suggestion visible before pagination", visible, 180
            )
            pair = (await api.get(f"/api/v1/matches/{pair_id}")).json()
            assert pair["classification"]["event"]["confidence"] == 0.1
            assert pair["relationship"] == "unverified" and pair["review"] is None
            assert not (await api.get("/api/v1/opportunities", params={"q": "CONTROLH"})).json()
            response = await api.get("/api/v1/discovery/coverage")
            response.raise_for_status()
            coverage = response.json()
            assert coverage["contracts"] >= 31
            (self.directory / "discovery-pair.json").write_text(json.dumps(pair))
            (self.directory / "coverage.json").write_text(json.dumps(coverage, indent=2))
            if browser:
                standalone = self.web_directory / ".next/standalone"
                server = standalone / "server.js"
                if not server.exists():
                    server = standalone / "apps/web/server.js"
                if not server.exists():
                    raise RuntimeError("Build the standalone web app before connected acceptance")
                shutil.copytree(
                    self.web_directory / ".next/static",
                    server.parent / ".next/static",
                    dirs_exist_ok=True,
                )
                if (self.web_directory / "public").exists():
                    shutil.copytree(
                        self.web_directory / "public", server.parent / "public", dirs_exist_ok=True
                    )
                self.env.update(PORT=str(self.web_port), HOSTNAME="127.0.0.1")
                self.start(
                    "web",
                    ["node", str(server)],
                    server.parent,
                )

                async def ready():
                    try:
                        async with httpx.AsyncClient(timeout=30) as web:
                            return (
                                await web.get(f"http://127.0.0.1:{self.web_port}/markets")
                            ).status_code == 200
                    except httpx.TransportError:
                        return False

                await self.wait("Production Next.js connected to discovery backend", ready)
                env = {
                    **self.env,
                    "ARBBOT_ACCEPTANCE_WEB_URL": f"http://127.0.0.1:{self.web_port}",
                    "ARBBOT_ACCEPTANCE_OUTPUT": str(self.directory),
                    "ARBBOT_ACCEPTANCE_CONTROL": str(self.control),
                }
                await asyncio.to_thread(
                    subprocess.run,
                    [
                        "npm",
                        "run",
                        "test:acceptance",
                        "--",
                        "discovery-workflow.spec.ts",
                        "--output",
                        str(self.directory / "browser-results"),
                    ],
                    cwd=ROOT / "apps/web",
                    env=env,
                    check=True,
                )
                self.results.append("Connected production desktop/mobile discovery workflow")
            (self.directory / "discovery-results.json").write_text(
                json.dumps(
                    {
                        "results": self.results,
                        "completed_at_epoch": time.time(),
                        "model_evidence": "Scripted transport; model quality measured separately.",
                        "financial_evidence": "Synthetic positives; no real arbitrage claimed.",
                    },
                    indent=2,
                )
            )


async def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    harness = DiscoveryHarness(args.output, args.database_url, args.web_dir)
    try:
        await harness.run(not args.no_browser)
    except Exception:
        await harness.diagnostics()
        raise
    finally:
        await harness.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--web-dir", type=Path, default=ROOT / "apps/web")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--database-url", default="postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot"
    )
    asyncio.run(main(parser.parse_args()))
