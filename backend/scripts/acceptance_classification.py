"""Scripted offline Decisions fixtures, explicitly excluded from model accuracy metrics."""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from arbbot.domain import Market, restore, utcnow
from arbbot.matching.classification_input import build_request
from arbbot.matching.service import retrieve_candidates
from arbbot.storage.models import MarketRecord


async def write_recording(database, path):
    async with database.sessions() as session:
        markets = [
            restore(Market, row.payload)
            for row in (
                await session.scalars(select(MarketRecord).where(MarketRecord.mode == "live"))
            ).all()
        ]
        pairs, _ = retrieve_candidates(markets, {}, [], supplement=20)
        responses = {}
        for left, right in pairs:
            if left.external_id.removeprefix("SYN-") != right.external_id.removeprefix(
                "synthetic-"
            ) or left.external_id not in {f"SYN-{i}" for i in range(1, 6)}:
                continue
            built = await build_request(session, "live", (left.id, right.id), "typesafe/jev-1.13")
            if not built:
                continue
            _, request = built
            # This is a scripted provider-contract fixture, not an observed Jev prediction.
            same = (
                left.external_id.removeprefix("SYN-")
                == right.external_id.removeprefix("synthetic-").split("-")[0]
            )
            answers = {}
            for key, question in request["questions"].items():
                options = question["criteria"]
                if key == "event":
                    choice = "same_event" if same else "different_event"
                elif key.endswith("evidence"):
                    choice = next(
                        (
                            s["id"]
                            for s in request["state"]["spans"]
                            if s["id"] in options and s["applicability"] == "market_terms"
                        ),
                        "none",
                    )
                else:
                    choice = "same_meaning"
                answers[key] = {
                    "type": "choice",
                    "choice": choice,
                    "confidence": 0.95,
                    "probabilities": {c: 1 if c == choice else 0 for c in options},
                }
            responses["|".join(sorted((left.id, right.id)))] = {
                "model": "typesafe/jev-1.13-20260917",
                "answers": answers,
                "usage": {"cost": 0, "input_tokens": 0, "output_tokens": 0},
            }
    await asyncio.to_thread(
        Path(path).write_text,
        json.dumps(
            {"format": "scripted-decisions-acceptance-v1", "status": 200, "pairs": responses}
        )
        + "\n",
    )


async def verify(harness, api):
    from arbbot.sources.models import SourceCapture
    from arbbot.sources.repository import SourceRepository
    from arbbot.storage.repository import Repository

    await write_recording(harness.db, harness.classification_recording)

    async def suggestion():
        rows = (
            await api.get(
                "/api/v1/matches",
                params={"classification": "suggested", "market_id": "kalshi:SYN-5", "limit": 20},
            )
        ).json()
        harness.ai_pair = next(
            (m for m in rows if m["right_id"] == "polymarket_us:synthetic-5"), None
        )
        return bool(harness.ai_pair)

    await harness.wait(
        "Scripted Decisions response adds a differently worded unreviewed candidate",
        suggestion,
        deadline_seconds=240,
    )
    pair = harness.ai_pair
    assert (
        pair["ai_only"] and pair["status"] == "candidate" and not pair["comparison"]["same_event"]
    )
    detail = (await api.get(f"/api/v1/matches/{pair['id']}/classification")).json()
    assert detail["recorded"] and detail["clauses"] and detail["evidence"]
    assert not (
        await api.get("/api/v1/opportunities", params={"match_id": pair["id"]})
    ).json() or all(
        o["match_id"] != pair["id"] for o in (await api.get("/api/v1/opportunities")).json()
    )
    # Expired/changed source advice must disappear before the next matching publication.
    store = SourceRepository(harness.db)
    market = await Repository(harness.db).market("live", "kalshi:SYN-5")
    await store.record(
        SourceCapture(
            mode="live",
            venue="kalshi",
            market_id=market.id,
            url="https://assets.kalshi.com/acceptance/jev-source.txt",
            label="jev_test",
            content=b"SYNTHETIC source context changed. Cancellation refund policy revised.",
            content_type="text/plain",
            retrieved_at=utcnow(),
        )
    )
    assert (await api.get(f"/api/v1/matches/{pair['id']}/classification")).json()[
        "state"
    ] == "stale"
    historical = (
        await api.get(
            f"/api/v1/matches/{pair['id']}/classification", params={"run_id": detail["run_id"]}
        )
    ).json()
    assert historical["state"] == "stale" and not historical["supports_candidate"]
    # Force an outage while the new semantic input is classified.
    recording = json.loads(harness.classification_recording.read_text())
    recording["status"] = 503
    harness.classification_recording.write_text(json.dumps(recording))

    async def degraded():
        status = (await api.get("/api/v1/status")).json()
        return status["classification"]["state"] == "degraded"

    await harness.wait(
        "Classification provider outage is exposed independently", degraded, deadline_seconds=240
    )
    repository = Repository(harness.db)
    before = await repository.latest_books("live")

    async def books_progress():
        after = await repository.latest_books("live")
        return any(
            after[mid].received_at > book.received_at
            for mid, book in before.items()
            if mid in after
        )

    await harness.wait("Books advance during provider outage", books_progress, deadline_seconds=30)
    harness.results.append("Book polling continues during Decisions provider outage")
    await write_recording(harness.db, harness.classification_recording)
    await harness.wait(
        "Provider recovery reclassifies changed sources", suggestion, deadline_seconds=240
    )
    # Preserve the currently readable candidate for the connected browser checks.
    (harness.directory / "classification-pair.json").write_text(json.dumps(harness.ai_pair))
