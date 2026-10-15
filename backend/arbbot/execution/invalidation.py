"""Explain a historical estimate's failed current eligibility without changing its audit payload."""

from arbbot.domain import Market, restore, utcnow
from arbbot.execution.repository import ExecutionRepository
from arbbot.reviews.repository import ReviewRepository
from arbbot.storage.models import MarketRecord, MatchRecord, OpportunityRecord
from arbbot.storage.repository import aware


async def invalidation_reasons(repository, settings, opportunity):
    now, reasons, markets = utcnow(), [], []
    health = {
        row["venue"]: row
        for row in await repository.health(settings.mode, settings.health_timeout_seconds)
    }
    async with repository.database.sessions() as session:
        record = await session.get(OpportunityRecord, opportunity.id)
        if opportunity.valid_until <= now or (record and aware(record.valid_until) <= now):
            reasons.append("input_validity_expired")
        if not record or not record.active:
            reasons.append("evaluation_superseded_or_withdrawn")
        match = await session.get(MatchRecord, opportunity.match_id)
        if not match or not match.current:
            reasons.append("matching_generation_removed")
        for leg in opportunity.legs:
            row = await session.get(MarketRecord, f"{settings.mode}:{leg.market_id}")
            if not row:
                reasons.append(f"market_missing:{leg.market_id}")
                continue
            market = restore(Market, row.payload)
            markets.append(market)
            if market.venue not in settings.enabled_venues:
                reasons.append(f"venue_disabled:{market.venue}")
            if market.status != "open" or market.closes_at <= now:
                reasons.append(f"market_closed:{market.id}")
            if market.ingestion_issues:
                reasons.append(f"instrument_data_invalid:{market.id}")
            if row.latest_book_id != leg.book_id:
                reasons.append(f"quote_changed:{market.id}")
            venue = health.get(market.venue)
            feed = (
                next(
                    (f for f in venue.get("market_health", []) if f["market_id"] == market.id),
                    None,
                )
                if venue
                else None
            )
            if not venue or venue["status"] == "stale" or not venue.get("discovery_ok"):
                reasons.append(f"venue_feed_unavailable:{market.venue}")
            elif not feed or feed["status"] != "healthy":
                reasons.append(f"quote_feed_unavailable:{market.id}")
        automatic = opportunity.qualification is not None
        if automatic:
            from arbbot.qualification.service import current

            summary, _ = await current(session, settings.mode, opportunity.match_id)
            if summary.status != "qualified" or (
                summary.assessment_id != opportunity.qualification.assessment_id
            ):
                reasons.append("qualification_changed_or_expired")
        elif opportunity.review_revision_id:
            review = await ReviewRepository(repository.database).decision_in_session(
                session, settings.mode, opportunity.review.left_id, opportunity.review.right_id
            )
            if not review or review.revision.id != opportunity.review_revision_id:
                reasons.append("approval_revision_changed")
            if review and not review.eligible:
                reasons.extend(review.blocked_reasons)
        elif settings.mode == "live" and not repository.allow_file_reviews:
            reasons.append("approval_unverified")
        if opportunity.review and opportunity.review.expires_at <= now:
            reasons.append("approval_expired")
        from arbbot.qualification.providers import requires_context

        if settings.mode == "live" and (automatic or requires_context(markets)):
            configuration = ExecutionRepository(repository.database)
            context = await (
                configuration.public_context(session, settings.mode, markets)
                if automatic
                else configuration.context(session, settings.mode, markets)
            )
            reasons.extend(context.blocked_reasons)
            for label, current, bound in (
                ("access_profile", context.access_revision_id, opportunity.access_revision_id),
                (
                    "source_applicability",
                    context.applicability_revision_ids,
                    opportunity.applicability_revision_ids,
                ),
                ("fee_policy", context.fee_revision_ids, opportunity.fee_revision_ids),
            ):
                if current != bound:
                    reasons.append(f"{label}_revision_changed")
    return tuple(sorted(set(reasons))) or ("current_inputs_not_eligible",)
