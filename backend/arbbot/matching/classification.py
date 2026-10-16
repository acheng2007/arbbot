"""Durable advisory jobs, cache, immutable audit runs and bounded supervised execution."""

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

import httpx
from sqlalchemy import func, select

from arbbot.domain import digest, utcnow
from arbbot.matching.classification_input import (
    CLAUSES,
    VERSION,
    build_request,
    cache_hash,
    job_current,
)
from arbbot.matching.classification_models import (
    ClassificationRun,
    ClassificationSummary,
    EvidenceSpan,
    Finding,
)
from arbbot.matching.classification_provider import (
    DecisionsProvider,
    ProviderFailure,
    RecordedDecisions,
    finding,
)
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import retrieve_candidates
from arbbot.storage.models import (
    ClassificationJobRecord,
    ClassificationRunRecord,
    ClassificationSchedulerRecord,
)
from arbbot.storage.repository import aware


def configured_state(settings):
    if not settings.classification_enabled or settings.mode != "live":
        return "disabled"
    if not settings.openrouter_api_key and not settings.classification_recording_file:
        return "unconfigured"
    return "pending"


async def summary(session, job):
    if not job:
        return ClassificationSummary(state="pending")
    row = await session.get(ClassificationRunRecord, job.run_id) if job.run_id else None
    value = (
        ClassificationRun.model_validate(row.payload).summary
        if row
        else ClassificationSummary(
            state="pending", input_hash=job.input_hash, requested_model=job.request["model"]
        )
    )
    current = await job_current(session, job)
    if not current or (value.expires_at and value.expires_at <= utcnow()):
        return value.model_copy(update={"state": "stale", "supports_candidate": False})
    if job.state in ("pending", "running"):
        return value.model_copy(update={"state": "pending", "supports_candidate": False})
    return value


class ClassificationService:
    def __init__(self, settings, database, changed=None, retrieval=None):
        self.settings, self.database = settings, database
        self.changed = changed or asyncio.Event()
        self.provider = None
        self.busy = set()
        self.retrieval = retrieval
        self.advised_pairs = set()

    async def schedule(self, markets, definitions=(), reviews=()):
        if configured_state(self.settings) != "pending":
            return
        if not definitions and not reviews:
            from arbbot.reviews.repository import ReviewRepository

            definitions, states = await ReviewRepository(self.database).snapshot(
                self.settings.mode, [m.id for m in markets]
            )
            reviews = [s.revision for s in states]

        def retrieve():
            supplied = {d.market_id: d for d in definitions}
            contracts = {
                m.id: supplied.get(m.id) or extract_contract(m).definition for m in markets
            }
            pairs, limited = retrieve_candidates(markets, contracts, reviews, supplement=20)
            indexed = {m.id: m for m in markets}
            keys = {tuple(sorted((a.id, b.id))) for a, b in pairs}
            if self.retrieval:
                keys.update(self.retrieval.current_pairs(markets))
            return [(indexed[a], indexed[b]) for a, b in sorted(keys)], limited

        pairs, _ = await asyncio.to_thread(retrieve)
        if self.settings.classification_recording_file:
            recording = json.loads(
                await asyncio.to_thread(self.settings.classification_recording_file.read_text)
            )
            declared = set(recording.get("pairs", {}))
            pairs = [(a, b) for a, b in pairs if "|".join(sorted((a.id, b.id))) in declared]
        if not pairs:
            return
        async with self.database.sessions.begin() as session:
            scheduler = await session.get(ClassificationSchedulerRecord, self.settings.mode)
            payload = dict(scheduler.payload) if scheduler else {}
            cursor = payload.get("cursor", "")
            ordered = sorted((digest([a.mode, *sorted((a.id, b.id))]), a, b) for a, b in pairs)
            ordered = [p for p in ordered if p[0] > cursor] + [p for p in ordered if p[0] <= cursor]
            pending = await session.scalar(
                select(func.count())
                .select_from(ClassificationJobRecord)
                .where(
                    ClassificationJobRecord.mode == self.settings.mode,
                    ClassificationJobRecord.state.in_(("pending", "running")),
                )
            )
            for mid, a, b in ordered[:32]:
                if pending >= 512:
                    break
                key = f"{self.settings.mode}:{mid}"
                job = await session.get(ClassificationJobRecord, key)
                if key in self.busy:
                    continue
                if job:
                    value = await summary(session, job)
                    if value.state in ("fresh", "pending"):
                        payload["cursor"] = mid
                        continue
                    # Failed requests are retried in later rotations after a cooldown.
                    if (
                        value.state == "unavailable"
                        and aware(job.updated_at) + timedelta(seconds=60) > utcnow()
                    ):
                        payload["cursor"] = mid
                        continue
                built = await build_request(
                    session, self.settings.mode, (a.id, b.id), self.settings.classification_model
                )
                if not built:
                    continue
                fingerprint, request = built
                input_hash = cache_hash(fingerprint, request["model"])
                cached = (
                    await session.scalars(
                        select(ClassificationRunRecord)
                        .where(
                            ClassificationRunRecord.mode == self.settings.mode,
                            ClassificationRunRecord.match_id == mid,
                            ClassificationRunRecord.input_hash == input_hash,
                            ClassificationRunRecord.completed_at > utcnow() - timedelta(hours=24),
                        )
                        .order_by(ClassificationRunRecord.completed_at.desc())
                    )
                ).all()
                reusable = next(
                    (
                        r
                        for r in cached
                        if r.payload["applied"] and r.payload["summary"]["state"] == "fresh"
                    ),
                    None,
                )
                if reusable:
                    await session.merge(
                        ClassificationJobRecord(
                            key=key,
                            mode=self.settings.mode,
                            match_id=mid,
                            input_hash=input_hash,
                            request=request,
                            semantic_inputs=fingerprint,
                            state="fresh",
                            run_id=reusable.id,
                            updated_at=utcnow(),
                        )
                    )
                    payload["cursor"] = mid
                    continue
                if job:
                    job.input_hash, job.request, job.state, job.run_id = (
                        input_hash,
                        request,
                        "pending",
                        None,
                    )
                    job.semantic_inputs = fingerprint
                    job.updated_at = utcnow()
                else:
                    session.add(
                        ClassificationJobRecord(
                            key=key,
                            mode=self.settings.mode,
                            match_id=mid,
                            input_hash=input_hash,
                            request=request,
                            semantic_inputs=fingerprint,
                            state="pending",
                            updated_at=utcnow(),
                        )
                    )
                pending += 1
                payload["cursor"] = mid
            await session.merge(
                ClassificationSchedulerRecord(mode=self.settings.mode, payload=payload)
            )

    async def advice(self, mode):
        output = {}
        retained = set()
        async with self.database.sessions() as session:
            session.info["classification_identity_cache"] = {}
            jobs = (
                await session.scalars(
                    select(ClassificationJobRecord).where(ClassificationJobRecord.mode == mode)
                )
            ).all()
            for job in jobs:
                output[job.match_id] = await summary(session, job)
                if output[job.match_id].supports_candidate:
                    retained.add(tuple(sorted(m["id"] for m in job.request["state"]["markets"])))
        self.advised_pairs = retained
        return output

    async def process(self, key):
        async with self.database.sessions.begin() as session:
            job = await session.get(ClassificationJobRecord, key, with_for_update=True)
            if not job or job.state != "pending":
                return
            if not await job_current(session, job):
                job.state = "stale"
                return
            job.state = "running"
            semantic_inputs = job.semantic_inputs
            request, input_hash, mid, mode = job.request, job.input_hash, job.match_id, job.mode
        started = utcnow()
        error, result, attempts = None, None, 0
        try:
            result, attempts = await self.provider.decide(request)
        except ProviderFailure as exc:
            error, attempts = exc.code, exc.attempts
        now, run_id = utcnow(), uuid4().hex
        event, clauses = None, {}
        spans = [EvidenceSpan.model_validate(s) for s in request["state"]["spans"]]
        if result:
            event_ids = tuple(
                result.answers[f"event_{side}_evidence"].choice for side in ("left", "right")
            )
            event = finding(
                result.answers["event"], tuple(s.id for s in spans if s.id in event_ids)
            )
            for clause in CLAUSES:
                selected = tuple(
                    result.answers[f"{clause}_{side}_evidence"].choice for side in ("left", "right")
                )
                evidence = [s for s in spans if s.id in selected]
                usable = len(evidence) == 2 and all(
                    s.applicability in ("verified", "market_terms") for s in evidence
                )
                clauses[clause] = (
                    finding(result.answers[clause], tuple(s.id for s in evidence))
                    if usable
                    else Finding(
                        choice="insufficient_evidence",
                        confidence=0,
                        probabilities={
                            "same_meaning": 0,
                            "different_meaning": 0,
                            "insufficient_evidence": 1,
                        },
                        evidence_ids=tuple(s.id for s in evidence),
                    )
                )
        supported = bool(event and event.choice == "same_event")
        value = ClassificationSummary(
            state="unavailable" if error else "fresh",
            run_id=run_id,
            input_hash=input_hash,
            event=event,
            outcome_relation=finding(
                result.answers["orientation"], tuple(s.id for s in spans if s.id in event_ids)
            )
            if result and "orientation" in result.answers
            else None,
            clauses=clauses,
            evidence=tuple(spans),
            requested_model=request["model"],
            returned_model=result.model if result else None,
            question_version=VERSION,
            started_at=started,
            completed_at=now,
            expires_at=now + timedelta(hours=24) if result else None,
            limitations=tuple(request["state"]["limitations"]),
            error=error,
            recorded=bool(self.settings.classification_recording_file),
            supports_candidate=supported,
        )
        async with self.database.sessions.begin() as session:
            from arbbot.sources.versions import lock_document
            from arbbot.storage.models import MarketRecord

            for market in request["state"]["markets"]:
                await session.get(MarketRecord, f"{mode}:{market['id']}", with_for_update=True)
            job = await session.get(ClassificationJobRecord, key, with_for_update=True)
            if job:
                from arbbot.matching.classification_input import identity

                fingerprint = await identity(
                    session, mode, [m["id"] for m in request["state"]["markets"]]
                )
                for url in sorted(
                    {d["url"] for d in fingerprint["documents"]} if fingerprint else ()
                ):
                    await lock_document(session, mode, url)
            applied = bool(job and job.input_hash == input_hash and await job_current(session, job))
            run = ClassificationRun(
                id=run_id,
                match_id=mid,
                mode=mode,
                input_hash=input_hash,
                request=request,
                summary=value,
                response=result.model_dump(mode="json") if result else None,
                usage=result.usage if result else {},
                attempts=attempts,
                applied=applied,
                semantic_inputs=semantic_inputs,
            )
            session.add(
                ClassificationRunRecord(
                    id=run_id,
                    match_id=mid,
                    mode=mode,
                    input_hash=input_hash,
                    completed_at=now,
                    payload=run.model_dump(mode="json"),
                )
            )
            await session.flush()
            if job and job.input_hash == input_hash:
                job.run_id, job.state, job.updated_at = (
                    run_id,
                    value.state if applied else "stale",
                    now,
                )
            scheduler = await session.get(ClassificationSchedulerRecord, mode)
            health = dict(scheduler.payload) if scheduler else {}
            health.update(
                error=error or (health.get("error") if self.provider.paused else None),
                paused=self.provider.paused,
            )
            if result:
                health["last_success"] = now.isoformat()
            await session.merge(ClassificationSchedulerRecord(mode=mode, payload=health))
        self.changed.set()

    async def supervised_process(self, key):
        try:
            await self.process(key)
        except Exception:
            async with self.database.sessions.begin() as session:
                job = await session.get(ClassificationJobRecord, key)
                if job and job.state == "running":
                    job.state = "pending"
                scheduler = await session.get(ClassificationSchedulerRecord, self.settings.mode)
                data = dict(scheduler.payload) if scheduler else {}
                data["error"] = "classification_job_error"
                await session.merge(
                    ClassificationSchedulerRecord(mode=self.settings.mode, payload=data)
                )

    async def run(self, stop, catalog_markets):
        if configured_state(self.settings) != "pending":
            return
        recording = (
            RecordedDecisions(self.settings.classification_recording_file)
            if self.settings.classification_recording_file
            else None
        )
        async with httpx.AsyncClient(
            transport=recording.transport if recording else None, follow_redirects=False
        ) as client:
            self.provider = DecisionsProvider(
                client,
                self.settings.openrouter_api_key.get_secret_value()
                if self.settings.openrouter_api_key
                else "recorded",
                self.settings.classification_requests_per_second,
            )
            # A crashed process leaves durable running jobs. Requeue before resuming.
            async with self.database.sessions.begin() as session:
                jobs = (
                    await session.scalars(
                        select(ClassificationJobRecord).where(
                            ClassificationJobRecord.mode == self.settings.mode,
                            ClassificationJobRecord.state == "running",
                        )
                    )
                ).all()
                for job in jobs:
                    job.state = "pending"
            tasks = set()
            try:
                while not stop.is_set():
                    try:
                        if not self.provider.paused:
                            await self.schedule(await catalog_markets())
                            async with self.database.sessions() as session:
                                keys = (
                                    await session.scalars(
                                        select(ClassificationJobRecord.key)
                                        .where(
                                            ClassificationJobRecord.mode == self.settings.mode,
                                            ClassificationJobRecord.state == "pending",
                                        )
                                        .order_by(
                                            ClassificationJobRecord.updated_at,
                                            ClassificationJobRecord.key,
                                        )
                                        .limit(512)
                                    )
                                ).all()
                            for key in keys:
                                if len(tasks) >= 4:
                                    break
                                if key not in self.busy:
                                    self.busy.add(key)
                                    task = asyncio.create_task(self.supervised_process(key))
                                    tasks.add(task)

                                    def finished(done, job_key=key):
                                        tasks.discard(done)
                                        self.busy.discard(job_key)
                                        if not done.cancelled():
                                            done.exception()

                                    task.add_done_callback(finished)
                    except Exception:
                        # No source/provider exception is allowed to break book supervision.
                        async with self.database.sessions.begin() as session:
                            row = await session.get(
                                ClassificationSchedulerRecord, self.settings.mode
                            )
                            data = dict(row.payload) if row else {}
                            data["error"] = "classification_scheduler_error"
                            await session.merge(
                                ClassificationSchedulerRecord(mode=self.settings.mode, payload=data)
                            )
                    try:
                        await asyncio.wait_for(stop.wait(), 1)
                    except TimeoutError:
                        pass
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)


async def classification_health(database, settings):
    async with database.sessions() as session:
        row = await session.get(ClassificationSchedulerRecord, settings.mode)
        count = await session.scalar(
            select(func.count())
            .select_from(ClassificationJobRecord)
            .where(
                ClassificationJobRecord.mode == settings.mode,
                ClassificationJobRecord.state.in_(("pending", "running")),
            )
        )
    data = row.payload if row else {}
    state = configured_state(settings)
    return {
        "state": state
        if state != "pending"
        else "paused"
        if data.get("paused")
        else "degraded"
        if data.get("error")
        else "healthy",
        "queued": count,
        "last_success": data.get("last_success"),
        "error": data.get("error"),
        "recorded": bool(settings.classification_recording_file),
    }
