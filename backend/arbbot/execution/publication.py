"""Final transaction guard over exact market, book, health and configuration versions."""

from arbbot.domain import Book, Market, restore, utcnow
from arbbot.execution.repository import ExecutionRepository
from arbbot.quality import book_issue
from arbbot.storage.models import HealthRecord, MarketRecord, SnapshotRecord


async def guard_execution(database, session, mode, evaluations, settings):
    guarded = []
    configuration = ExecutionRepository(database)
    for result in evaluations:
        accepted, reasons = [], []
        for opportunity in result.opportunities:
            markets, books = [], []
            now = utcnow()
            for leg in opportunity.legs:
                row = await session.get(
                    MarketRecord, f"{mode}:{leg.market_id}", with_for_update=True
                )
                if not row or row.latest_book_id != leg.book_id:
                    reasons.append("quote_changed_before_publication")
                    break
                market = restore(Market, row.payload)
                snapshot = await session.get(SnapshotRecord, leg.book_id)
                book = Book.model_validate(snapshot.payload)
                health = await session.get(HealthRecord, f"{mode}:{market.venue}")
                feed = (
                    next(
                        (
                            f
                            for f in health.payload.get("market_health", [])
                            if f["market_id"] == market.id
                        ),
                        None,
                    )
                    if health
                    else None
                )
                if (
                    market.venue not in settings.enabled_venues
                    or market.status != "open"
                    or market.closes_at <= now
                    or book_issue(market, book, now, settings.max_quote_age_seconds)
                    or not health
                    or not health.payload.get("discovery_ok")
                    or not feed
                    or feed["status"] != "healthy"
                    or feed["book_id"] != book.id
                ):
                    reasons.append("input_invalid_before_publication")
                    break
                markets.append(market)
                books.append(book)
            else:
                if (
                    abs((books[0].effective_at - books[1].effective_at).total_seconds())
                    > (settings.max_quote_skew_seconds)
                    or opportunity.valid_until <= now
                ):
                    reasons.append("quote_expired_or_unsynchronized_before_publication")
                    continue
                if mode == "live" and any(m.venue == "polymarket_us" for m in markets):
                    context = await configuration.context(session, mode, markets, lock=True)
                    if context.blocked_reasons or (
                        context.access_revision_id != opportunity.access_revision_id
                        or context.applicability_revision_ids
                        != opportunity.applicability_revision_ids
                        or context.fee_revision_ids != opportunity.fee_revision_ids
                    ):
                        reasons.append("execution_configuration_changed_before_publication")
                        continue
                accepted.append(opportunity)
        guarded.append(
            result.model_copy(
                update={
                    "opportunities": tuple(accepted),
                    "status": "profitable" if accepted else "invalid" if reasons else result.status,
                    "blocked_reasons": (*result.blocked_reasons, *sorted(set(reasons))),
                }
            )
        )
    return guarded
