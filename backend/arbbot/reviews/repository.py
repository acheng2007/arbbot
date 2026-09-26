"""Transactional revisions. Only head pointers mutate; every prior payload is retained."""

from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from arbbot.domain import Market, restore, utcnow
from arbbot.matching.contracts import compare_contracts, definition_hash, evidence_issues
from arbbot.matching.settlement import settlement_issues
from arbbot.reviews.models import (
    Actor,
    DecisionRevision,
    DecisionState,
    DecisionWrite,
    DraftRevision,
    DraftWrite,
    ReviewValidationError,
    RevisionConflict,
    pair_key,
    payload,
)
from arbbot.storage.models import (
    DecisionHeadRecord,
    DecisionRevisionRecord,
    DraftHeadRecord,
    DraftRevisionRecord,
    MarketRecord,
    SourceArtifactRecord,
)
from arbbot.storage.repository import aware


class ReviewRepository:
    def __init__(self, database):
        self.database = database

    @asynccontextmanager
    async def _write(self):
        async with self.database.sessions.begin() as session:
            # SQLite lacks row locks. Acquire its write lock before reading the
            # expected head so concurrent edits have the same CAS semantics.
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            yield session

    @asynccontextmanager
    async def _read(self):
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "postgresql":
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            elif self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN"))
            yield session

    @staticmethod
    async def _market(session, mode, market_id, *, lock=False):
        row = await session.get(MarketRecord, f"{mode}:{market_id}", with_for_update=lock)
        if row is None:
            raise LookupError("Market not found in this data mode")
        return restore(Market, row.payload)

    @staticmethod
    async def _draft(session, mode, revision_id):
        row = await session.get(DraftRevisionRecord, revision_id)
        if row is None or not row.market_key.startswith(mode + ":"):
            raise LookupError("Draft revision not found in this data mode")
        return DraftRevision.model_validate(row.payload)

    @staticmethod
    async def _source_issues(session, market, ids):
        if not ids:
            return []
        rows = (
            await session.execute(
                select(
                    SourceArtifactRecord.id,
                    SourceArtifactRecord.url,
                    SourceArtifactRecord.label,
                    SourceArtifactRecord.status,
                    SourceArtifactRecord.last_seen_at,
                ).where(SourceArtifactRecord.market_key == f"{market.mode}:{market.id}")
            )
        ).all()
        by_id = {row.id: row for row in rows}
        latest = {}
        for row in rows:
            key = row.url, row.label
            previous = latest.get(key)
            if previous is None or (aware(row.last_seen_at), row.id) > (
                aware(previous.last_seen_at),
                previous.id,
            ):
                latest[key] = row
        issues = []
        for artifact_id in ids:
            row = by_id.get(artifact_id)
            if row is None or row.status != "captured":
                issues.append(f"source_missing_or_wrong_market:{artifact_id}")
            elif latest[(row.url, row.label)].id != row.id:
                issues.append(f"source_changed:{artifact_id}")
        return issues

    async def save_draft(self, mode, market_id, request: DraftWrite, actor: Actor):
        try:
            async with self._write() as session:
                market = await self._market(session, mode, market_id, lock=True)
                key = f"{mode}:{market_id}"
                head = await session.get(DraftHeadRecord, key)
                current = head.revision_id if head else None
                if current != request.expected_revision_id:
                    raise RevisionConflict("Draft changed; reload the current revision", current)
                if (
                    request.definition.market_id != market_id
                    or request.definition.terms_hash != market.terms_hash
                ):
                    raise RevisionConflict(
                        "Market terms changed; reload its source evidence", current
                    )
                issues = evidence_issues(market, request.definition)
                issues += await self._source_issues(session, market, request.source_artifact_ids)
                if issues:
                    raise ReviewValidationError(issues)
                previous = await self._draft(session, mode, current) if current else None
                result = DraftRevision(
                    id=uuid4().hex,
                    previous_revision_id=current,
                    revision=previous.revision + 1 if previous else 1,
                    market=market,
                    definition=request.definition,
                    definition_hash=definition_hash(request.definition),
                    source_artifact_ids=request.source_artifact_ids,
                    actor=actor,
                    created_at=utcnow(),
                    reason=request.reason,
                )
                session.add(
                    DraftRevisionRecord(
                        id=result.id,
                        market_key=key,
                        previous_revision_id=current,
                        revision=result.revision,
                        payload=payload(result),
                    )
                )
                await session.flush()
                if head is None:
                    session.add(DraftHeadRecord(market_key=key, revision_id=result.id))
                else:
                    changed = await session.execute(
                        update(DraftHeadRecord)
                        .where(
                            DraftHeadRecord.market_key == key,
                            DraftHeadRecord.revision_id == current,
                        )
                        .values(revision_id=result.id)
                    )
                    if changed.rowcount != 1:
                        raise RevisionConflict("Draft changed; reload the current revision")
                return result
        except IntegrityError as exc:
            current = await self.current_draft(mode, market_id)
            raise RevisionConflict(
                "Draft changed; reload the current revision", current.id if current else None
            ) from exc

    async def current_draft(self, mode, market_id):
        async with self.database.sessions() as session:
            head = await session.get(DraftHeadRecord, f"{mode}:{market_id}")
            return await self._draft(session, mode, head.revision_id) if head else None

    async def draft_revision(self, mode, revision_id):
        async with self.database.sessions() as session:
            return await self._draft(session, mode, revision_id)

    async def draft_history(self, mode, market_id, *, limit=100, offset=0):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(DraftRevisionRecord)
                    .where(DraftRevisionRecord.market_key == f"{mode}:{market_id}")
                    .order_by(DraftRevisionRecord.revision.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [DraftRevision.model_validate(row.payload) for row in rows]

    async def _draft_issues(self, session, draft, market):
        issues = []
        if market.terms_hash != draft.definition.terms_hash:
            issues.append("market_terms_changed")
        head = await session.get(DraftHeadRecord, f"{market.mode}:{market.id}")
        if head is None or head.revision_id != draft.id:
            issues.append("draft_changed")
        issues += await self._source_issues(session, market, draft.source_artifact_ids)
        return issues

    async def save_decision(self, mode, request: DecisionWrite, actor: Actor):
        try:
            async with self._write() as session:
                left = await self._draft(session, mode, request.left_draft_id)
                right = await self._draft(session, mode, request.right_draft_id)
                if left.market.venue == right.market.venue:
                    raise ReviewValidationError(["cross_venue_pair_required"])
                markets = {}
                # A consistent lock order prevents opposite pair orientations
                # from deadlocking while either market or draft is being edited.
                for market_id in sorted((left.market.id, right.market.id)):
                    markets[market_id] = await self._market(session, mode, market_id, lock=True)
                key = pair_key(mode, left.market.id, right.market.id)
                head = await session.get(DecisionHeadRecord, key)
                current = head.revision_id if head else None
                if current != request.expected_revision_id:
                    raise RevisionConflict("Review changed; reload the current decision", current)
                if request.action == "revoked" and head is None:
                    raise ReviewValidationError(["no_previous_decision_to_revoke"])
                review = request.review
                if request.action == "verified":
                    issues = []
                    incomplete = []
                    for side, draft in (("left", left), ("right", right)):
                        market = markets[draft.market.id]
                        issues += [
                            f"{side}:{issue}"
                            for issue in await self._draft_issues(session, draft, market)
                        ]
                        if mode == "live" and (
                            not draft.source_artifact_ids
                            or market.settlement_details.get("source_status") != "captured"
                        ):
                            incomplete.append(f"{side}:current_source_evidence_required")
                    if issues:
                        raise RevisionConflict(
                            "Reviewed inputs changed; reload the current drafts and sources",
                            current,
                            issues=issues,
                        )
                    if incomplete:
                        raise ReviewValidationError(incomplete)
                    if mode == "live" and (
                        issues := settlement_issues(review, left.definition, right.definition)
                    ):
                        raise ReviewValidationError(issues)
                    comparison = compare_contracts(
                        markets[left.market.id],
                        markets[right.market.id],
                        left.definition,
                        right.definition,
                    )
                    if comparison.status != "compatible":
                        raise ReviewValidationError(
                            ["settlement_comparison_not_compatible", *comparison.issues]
                        )
                    if (
                        (review.left_id, review.right_id) != (left.market.id, right.market.id)
                        or (review.left_terms_hash, review.right_terms_hash)
                        != (left.market.terms_hash, right.market.terms_hash)
                        or (review.left_definition_hash, review.right_definition_hash)
                        != (left.definition_hash, right.definition_hash)
                    ):
                        raise RevisionConflict(
                            "Approval must bind the exact current draft hashes", current
                        )
                    if review.expires_at <= utcnow():
                        raise ReviewValidationError(["approval_expired"])
                    review = review.model_copy(update={"reviewer": actor.audit_id})
                previous = await session.get(DecisionRevisionRecord, current) if current else None
                result = DecisionRevision(
                    id=uuid4().hex,
                    previous_revision_id=current,
                    revision=previous.revision + 1 if previous else 1,
                    mode=mode,
                    pair_key=key,
                    left_id=left.market.id,
                    right_id=right.market.id,
                    left_draft_id=left.id,
                    right_draft_id=right.id,
                    action=request.action,
                    reason=request.reason,
                    review=review,
                    actor=actor,
                    created_at=utcnow(),
                )
                session.add(
                    DecisionRevisionRecord(
                        id=result.id,
                        mode=mode,
                        pair_key=key,
                        previous_revision_id=current,
                        left_draft_id=left.id,
                        right_draft_id=right.id,
                        revision=result.revision,
                        payload=payload(result),
                    )
                )
                await session.flush()
                if head is None:
                    session.add(DecisionHeadRecord(pair_key=key, mode=mode, revision_id=result.id))
                else:
                    changed = await session.execute(
                        update(DecisionHeadRecord)
                        .where(
                            DecisionHeadRecord.pair_key == key,
                            DecisionHeadRecord.revision_id == current,
                        )
                        .values(revision_id=result.id)
                    )
                    if changed.rowcount != 1:
                        raise RevisionConflict("Review changed; reload the current decision")
                return result
        except IntegrityError as exc:
            raise RevisionConflict("Review changed; reload the current decision") from exc

    async def decision_history(self, mode, left_id, right_id, *, limit=100, offset=0):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(DecisionRevisionRecord)
                    .where(DecisionRevisionRecord.pair_key == pair_key(mode, left_id, right_id))
                    .order_by(DecisionRevisionRecord.revision.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [DecisionRevision.model_validate(row.payload) for row in rows]

    async def _state(self, session, revision):
        if revision.action != "verified":
            return DecisionState(
                revision=revision, eligible=False, blocked_reasons=(f"review_{revision.action}",)
            )
        issues = []
        if revision.review.expires_at <= utcnow():
            issues.append("approval_expired")
        definitions = []
        for side, draft_id, market_id in (
            ("left", revision.left_draft_id, revision.left_id),
            ("right", revision.right_draft_id, revision.right_id),
        ):
            draft = await self._draft(session, revision.mode, draft_id)
            definitions.append(draft.definition)
            market = await self._market(session, revision.mode, market_id)
            issues += [
                f"{side}:{issue}" for issue in await self._draft_issues(session, draft, market)
            ]
        if revision.mode == "live":
            issues.extend(settlement_issues(revision.review, *definitions))
        return DecisionState(revision=revision, eligible=not issues, blocked_reasons=tuple(issues))

    async def current_decision(self, mode, left_id, right_id):
        async with self._read() as session:
            return await self.decision_in_session(session, mode, left_id, right_id)

    async def decision_in_session(self, session, mode, left_id, right_id):
        head = await session.get(DecisionHeadRecord, pair_key(mode, left_id, right_id))
        if head is None:
            return None
        row = await session.get(DecisionRevisionRecord, head.revision_id)
        return await self._state(session, DecisionRevision.model_validate(row.payload))

    async def snapshot(self, mode, market_ids):
        """Read draft and decision heads from one database snapshot for a worker cycle."""
        if not market_ids:
            return [], []
        async with self._read() as session:
            drafts = (
                await session.scalars(
                    select(DraftRevisionRecord)
                    .join(DraftHeadRecord, DraftHeadRecord.revision_id == DraftRevisionRecord.id)
                    .where(
                        DraftRevisionRecord.market_key.in_(
                            [f"{mode}:{market_id}" for market_id in market_ids]
                        )
                    )
                )
            ).all()
            decisions = (
                await session.scalars(
                    select(DecisionRevisionRecord)
                    .join(
                        DecisionHeadRecord,
                        DecisionHeadRecord.revision_id == DecisionRevisionRecord.id,
                    )
                    .where(
                        DecisionHeadRecord.mode == mode,
                        DecisionRevisionRecord.payload["left_id"].as_string().in_(market_ids),
                        DecisionRevisionRecord.payload["right_id"].as_string().in_(market_ids),
                    )
                )
            ).all()
            return (
                [DraftRevision.model_validate(row.payload).definition for row in drafts],
                [
                    await self._state(session, DecisionRevision.model_validate(row.payload))
                    for row in decisions
                ],
            )
