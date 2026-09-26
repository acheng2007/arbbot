"""Database approvals are authoritative; absent or invalid decisions never fall back to files."""

from sqlalchemy import text

from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets
from arbbot.reviews.repository import ReviewRepository
from arbbot.storage.models import MarketRecord


class ReviewProvider:
    def __init__(self, database):
        self.reviews = ReviewRepository(database)

    async def matches(self, mode, markets):
        definitions, states = await self.reviews.snapshot(mode, [m.id for m in markets])
        supplied = {d.market_id: d for d in definitions}
        definitions = [supplied.get(m.id) or extract_contract(m).definition for m in markets]
        approvals = [state.revision.review for state in states if state.eligible]
        indexed = {frozenset((s.revision.left_id, s.revision.right_id)): s for s in states}
        matches = match_markets(markets, approvals, definitions)
        results = []
        for match in matches:
            state = indexed.get(frozenset((match.left_id, match.right_id)))
            if state:
                changes = {"review_revision_id": state.revision.id}
                if not state.eligible:
                    changes.update(
                        status="rejected" if state.revision.action == "rejected" else "candidate",
                        reason="Database review is ineligible: " + ", ".join(state.blocked_reasons),
                    )
                match = match.model_copy(update=changes)
            results.append(match)
        return results


async def refresh_match(reviews, session, mode, match, *, allow_file_reviews=False):
    if match.status != "verified":
        return match
    if match.review_revision_id:
        state = await reviews.decision_in_session(session, mode, match.left_id, match.right_id)
        if not state or not state.eligible or state.revision.id != match.review_revision_id:
            return match.model_copy(
                update={
                    "status": "rejected"
                    if state and state.revision.action == "rejected"
                    else "candidate",
                    "reason": "Database approval changed; reevaluation required.",
                }
            )
    elif mode == "live" and not allow_file_reviews:
        return match.model_copy(
            update={
                "status": "candidate",
                "reason": "A current database approval is required.",
            }
        )
    return match


async def guard_publication(database, session, mode, matches, evaluations):
    guarded = [
        match for match in matches if match.review_revision_id and match.status == "verified"
    ]
    if not guarded:
        return matches, evaluations
    if database.engine.dialect.name == "sqlite":
        await session.execute(text("BEGIN IMMEDIATE"))
    # Review, draft, source and market mutations all serialize through these rows.
    for market_id in sorted({m for match in guarded for m in (match.left_id, match.right_id)}):
        await session.get(MarketRecord, f"{mode}:{market_id}", with_for_update=True)
    reviews = ReviewRepository(database)
    invalid = set()
    for match in guarded:
        state = await reviews.decision_in_session(session, mode, match.left_id, match.right_id)
        if (
            state is None
            or not state.eligible
            or state.revision.id != match.review_revision_id
            or state.revision.review != match.review
        ):
            invalid.add(match.id)
    return (
        [
            match.model_copy(
                update={"status": "candidate", "reason": "Approval changed before publication"}
            )
            if match.id in invalid
            else match
            for match in matches
        ],
        [
            result.model_copy(
                update={
                    "opportunities": (),
                    "blocked_reasons": (
                        *result.blocked_reasons,
                        "approval_changed_before_publication",
                    ),
                }
            )
            if result.match_id in invalid
            else result
            for result in evaluations
        ],
    )
