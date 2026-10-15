"""Durable coalesced automatic qualification; late results are audit-only."""

import asyncio
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select, text, update

from arbbot.domain import Market, digest, restore, utcnow
from arbbot.qualification.decision import decide
from arbbot.qualification.models import Assessment
from arbbot.qualification.providers import capabilities
from arbbot.qualification.rules import FAMILIES, VERSION
from arbbot.qualification.summary import QualificationSummary
from arbbot.sources.versions import bound_versions, latest_document
from arbbot.storage.models import (
    DecisionHeadRecord,
    DecisionRevisionRecord,
    DiscoveryProgressRecord,
    MarketRecord,
    QualificationJobRecord,
    QualificationRunRecord,
    SourceArtifactRecord,
)
from arbbot.storage.repository import aware

logger = logging.getLogger(__name__)


async def inputs(session, mode, pair, *, lock=False):
    markets, documents, providers = [], [], []
    if lock:
        # Every writer acquires market rows first, then shared document locks in
        # sorted order. Overlapping pairs cannot reverse the lock order.
        for mid in sorted(pair):
            await session.get(MarketRecord, f"{mode}:{mid}", with_for_update=True)
        artifact_ids = (
            await session.scalars(
                select(SourceArtifactRecord.id).where(
                    SourceArtifactRecord.market_key.in_([f"{mode}:{mid}" for mid in pair]),
                    SourceArtifactRecord.label != "fee_policy",
                )
            )
        ).all()
        await bound_versions(session, mode, artifact_ids, lock=True)
    for mid in pair:
        row = await session.get(MarketRecord, f"{mode}:{mid}", with_for_update=lock)
        if not row:
            return None
        market = restore(Market, row.payload)
        markets.append(market.model_dump(mode="json"))
        cap = capabilities(market.venue)
        providers.append([cap.evidence.version, cap.execution_version] if cap else ["unsupported"])
        rows = (
            await session.scalars(
                select(SourceArtifactRecord).where(
                    SourceArtifactRecord.market_key == row.key,
                    SourceArtifactRecord.label != "fee_policy",
                )
            )
        ).all()
        for url in sorted({row.url for row in rows}):
            current = await latest_document(session, mode, url)
            documents.append(
                {
                    "market_id": mid,
                    "url": url,
                    "generation": current.details.get("source_generation", 0),
                    "status": current.status,
                    "content_digest": current.content_digest,
                }
            )
    head = await session.get(DecisionHeadRecord, digest([mode, *sorted(pair)]))
    veto = None
    if head:
        revision = await session.get(DecisionRevisionRecord, head.revision_id)
        if revision and revision.payload["action"] in ("rejected", "revoked"):
            veto = revision.id
    semantic = {
        "markets": [{"id": m["id"], "terms": m["terms_hash"]} for m in markets],
        "documents": documents,
        "providers": providers,
        "veto": veto,
        "policy": VERSION,
        "families": {k: r.version for k, r in FAMILIES.items()},
    }
    return {"semantic": semantic, "markets": markets, "hash": digest(semantic)}


async def current(session, mode, match_id, *, lock=False):
    job = await session.get(QualificationJobRecord, f"{mode}:{match_id}")
    if not job:
        return QualificationSummary(), None
    value = await inputs(session, mode, job.pair, lock=lock)
    if value and value["semantic"]["veto"]:
        return QualificationSummary(
            status="incompatible",
            input_hash=value["hash"],
            blocked_reasons=("explicit_operator_veto",),
        ), None
    run = await session.get(QualificationRunRecord, job.run_id) if job.run_id else None
    result = Assessment.model_validate(run.payload) if run else None
    if value is None or value["hash"] != job.input_hash:
        return QualificationSummary(
            status="stale",
            assessment_id=job.run_id,
            blocked_reasons=("qualification_inputs_changed",),
        ), None
    if result and result.input_hash == value["hash"]:
        summary = result.summary
        if summary.expires_at <= utcnow():
            return summary.model_copy(
                update={
                    "status": "stale",
                    "blocked_reasons": ("qualification_expired",),
                }
            ), None
        return summary, result
    return QualificationSummary(status="pending", input_hash=value["hash"]), None


async def refresh_match(session, match, *, lock=False):
    summary, result = await current(session, match.mode, match.id, lock=lock)
    return match.model_copy(
        update={
            "qualification": summary,
            "settlement": result.settlement if result and summary.status == "qualified" else None,
            "review": None,
            "review_revision_id": None,
            "comparison": result.comparison if result and result.comparison else match.comparison,
            "status": "verified"
            if summary.status == "qualified"
            else (
                "rejected" if "explicit_operator_veto" in summary.blocked_reasons else "candidate"
            ),
            "reason": "Automatically qualified by current evidence rules."
            if summary.status == "qualified"
            else "Automatic qualification: " + summary.status,
        }
    )


class QualificationService:
    def __init__(self, settings, database, changed=None):
        self.settings, self.database, self.changed = settings, database, changed

    async def schedule(self, matches):
        """Bound durable pending work, rotate remaining catalog pairs fairly."""
        mode = self.settings.mode
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            progress = await session.get(
                DiscoveryProgressRecord, f"{mode}:qualification-cursor", with_for_update=True
            )
            offset = progress.payload.get("offset", 0) if progress else 0
            ordered = sorted(matches, key=lambda m: m.id)
            if not ordered:
                return
            offset %= len(ordered)
            pending = await session.scalar(
                select(func.count())
                .select_from(QualificationJobRecord)
                .where(
                    QualificationJobRecord.mode == mode,
                    QualificationJobRecord.state.in_(("pending", "running")),
                )
            )
            processed = 0
            for match in ordered[offset:] + ordered[:offset]:
                value = await inputs(session, mode, (match.left_id, match.right_id))
                if not value:
                    continue
                job = await session.get(QualificationJobRecord, f"{mode}:{match.id}")
                summary, _ = await current(session, mode, match.id) if job else (None, None)
                valid = summary and summary.status not in ("pending", "stale")
                if valid:
                    processed += 1
                    continue
                if job and job.input_hash == value["hash"] and job.state in ("pending", "running"):
                    processed += 1
                    continue
                if pending >= 512:
                    break
                was_queued = bool(job and job.state in ("pending", "running"))
                await session.merge(
                    QualificationJobRecord(
                        key=f"{mode}:{match.id}",
                        mode=mode,
                        match_id=match.id,
                        input_hash=value["hash"],
                        pair=[match.left_id, match.right_id],
                        state="pending",
                        run_id=None,
                        updated_at=utcnow(),
                    )
                )
                if not was_queued:
                    pending += 1
                processed += 1
            await session.merge(
                DiscoveryProgressRecord(
                    key=f"{mode}:qualification-cursor",
                    mode=mode,
                    venue="system",
                    payload={"offset": offset + max(1, processed)},
                )
            )

    async def process_one(self):
        mode = self.settings.mode
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            job = await session.scalar(
                select(QualificationJobRecord)
                .where(
                    QualificationJobRecord.mode == mode, QualificationJobRecord.state == "pending"
                )
                .order_by(QualificationJobRecord.updated_at, QualificationJobRecord.key)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not job:
                return False
            job.state, job.updated_at = "running", utcnow()
            key, match_id, pair, requested_hash = job.key, job.match_id, job.pair, job.input_hash
            value = await inputs(session, mode, pair)
        if not value:
            async with self.database.sessions.begin() as session:
                await session.execute(
                    update(QualificationJobRecord)
                    .where(
                        QualificationJobRecord.key == key,
                        QualificationJobRecord.input_hash == requested_hash,
                    )
                    .values(state="stale", updated_at=utcnow())
                )
            return True
        now, run_id = utcnow(), uuid4().hex
        evidence = []
        try:
            markets = [restore(Market, m) for m in value["markets"]]
            async with self.database.sessions() as session:
                for market in markets:
                    cap = capabilities(market.venue)
                    if cap is None:
                        raise ValueError("unsupported_venue")
                    evidence.append(await cap.evidence.resolve(session, market, 86400))
            expiry = min(
                now + timedelta(seconds=86400),
                *(e.expires_at for e in evidence),
            )
            status, reasons, comparison, settlement = await asyncio.to_thread(
                decide, *markets, evidence, expiry
            )
            if value["semantic"]["veto"]:
                status, reasons, settlement = "incompatible", ("explicit_operator_veto",), None
        except Exception as exc:
            status, reasons, comparison, settlement = (
                "unavailable",
                ("qualification_provider_" + type(exc).__name__,),
                None,
                None,
            )
            expiry = utcnow() + timedelta(seconds=30)
        summary = QualificationSummary(
            status=status,
            assessment_id=run_id,
            input_hash=value["hash"],
            policy_version=VERSION,
            completed_at=utcnow(),
            expires_at=expiry,
            blocked_reasons=reasons,
            evidence_ids=tuple(sorted({i for e in evidence for i in e.artifact_ids})),
        )
        result = Assessment(
            id=run_id,
            match_id=match_id,
            mode=mode,
            pair=tuple(pair),
            input_hash=value["hash"],
            summary=summary,
            comparison=comparison,
            settlement=settlement,
            started_at=now,
            inputs=value,
        )
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            latest = await inputs(session, mode, pair, lock=True)
            session.add(
                QualificationRunRecord(
                    id=run_id,
                    match_id=match_id,
                    mode=mode,
                    input_hash=value["hash"],
                    completed_at=summary.completed_at,
                    payload=result.model_dump(mode="json"),
                )
            )
            await session.flush()
            job = await session.get(QualificationJobRecord, key, with_for_update=True)
            if (
                job
                and job.input_hash == requested_hash
                and latest
                and (latest["hash"] == value["hash"] == requested_hash)
            ):
                job.run_id, job.state, job.updated_at = run_id, "complete", utcnow()
            elif job and job.input_hash == requested_hash:
                job.state, job.updated_at = "stale", utcnow()
        if self.changed:
            self.changed.set()
        return True

    async def run(self, stop):
        # Only one persistent worker owns this queue, like exchange polling.
        # Recover jobs interrupted by the preceding worker process.
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(QualificationJobRecord)
                .where(
                    QualificationJobRecord.mode == self.settings.mode,
                    QualificationJobRecord.state == "running",
                )
                .values(state="pending")
            )

        async def renew():
            while not stop.is_set():
                try:
                    async with self.database.sessions.begin() as session:
                        jobs = (
                            await session.scalars(
                                select(QualificationJobRecord).where(
                                    QualificationJobRecord.mode == self.settings.mode,
                                    QualificationJobRecord.state.in_(("running", "complete")),
                                )
                            )
                        ).all()
                        for job in jobs:
                            if job.state == "running":
                                expired = aware(job.updated_at) + timedelta(seconds=60) <= utcnow()
                            else:
                                run = await session.get(QualificationRunRecord, job.run_id)
                                expired = bool(
                                    run
                                    and Assessment.model_validate(run.payload).summary.expires_at
                                    <= utcnow()
                                )
                            if expired:
                                job.state, job.run_id, job.updated_at = "pending", None, utcnow()
                except Exception as exc:
                    logger.warning(
                        "qualification_renew_failed", extra={"error": type(exc).__name__}
                    )
                try:
                    await asyncio.wait_for(stop.wait(), 1)
                except TimeoutError:
                    pass

        async def worker():
            while not stop.is_set():
                try:
                    if await self.process_one():
                        continue
                except Exception as exc:
                    logger.warning("qualification_failed", extra={"error": type(exc).__name__})
                try:
                    await asyncio.wait_for(stop.wait(), 0.25)
                except TimeoutError:
                    pass

        async with asyncio.TaskGroup() as group:
            group.create_task(renew())
            for _ in range(4):
                group.create_task(worker())


async def health(database, mode):
    async with database.sessions() as session:
        counts = (
            await session.execute(
                select(QualificationJobRecord.state, func.count())
                .where(QualificationJobRecord.mode == mode)
                .group_by(QualificationJobRecord.state)
            )
        ).all()
        last = await session.scalar(
            select(QualificationRunRecord)
            .where(QualificationRunRecord.mode == mode)
            .order_by(QualificationRunRecord.completed_at.desc())
            .limit(1)
        )
        statuses = (
            await session.scalars(
                select(QualificationRunRecord).where(
                    QualificationRunRecord.id.in_(
                        select(QualificationJobRecord.run_id).where(
                            QualificationJobRecord.mode == mode
                        )
                    )
                )
            )
        ).all()
        qualified = sum(r.payload["summary"]["status"] == "qualified" for r in statuses)
        success = await session.scalar(
            select(QualificationRunRecord)
            .where(
                QualificationRunRecord.mode == mode,
                QualificationRunRecord.payload["summary"]["status"].as_string() != "unavailable",
            )
            .order_by(QualificationRunRecord.completed_at.desc())
            .limit(1)
        )
    return {
        "queued": dict(counts).get("pending", 0),
        "running": dict(counts).get("running", 0),
        "assessed": len(statuses),
        "last_assessed_qualified": qualified,
        "last_success": aware(success.completed_at).isoformat() if success else None,
        "queue_limit": 512,
        "workers": 4,
        "last_completion": aware(last.completed_at).isoformat() if last else None,
        "last_error": last.payload["summary"]["blocked_reasons"]
        if last and last.payload["summary"]["status"] == "unavailable"
        else [],
    }
