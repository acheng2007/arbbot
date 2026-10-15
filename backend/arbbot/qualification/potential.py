"""Conditional price gaps use quotes, never a fabricated settlement approval."""

from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select, update

from arbbot.arbitrage.engine import consume, fill, valid_price
from arbbot.domain import (
    POTENTIAL_ASSUMPTIONS,
    Market,
    Match,
    PotentialOpportunity,
    digest,
    restore,
    utcnow,
)
from arbbot.fees.executable import fee_bound
from arbbot.matching.contracts import EVENT_FIELDS
from arbbot.qualification.providers import is_short, native_price
from arbbot.qualification.summary import QualificationSummary
from arbbot.quality import book_issue
from arbbot.storage.models import MarketRecord, MatchRecord, PotentialRecord


def calculate(match, markets, books, settings, now, context=None):
    if match.status == "rejected" or (
        match.qualification and match.qualification.status == "incompatible"
    ):
        return []
    if (
        match.qualification
        and match.qualification.status == "qualified"
        and context
        and not context.blocked_reasons
    ):
        return []
    comparison = match.comparison
    if comparison and any(
        d.field in EVENT_FIELDS and d.status == "different" for d in comparison.differences
    ):
        return []
    if not (comparison and comparison.same_event) and not (
        match.classification
        and match.classification.state == "fresh"
        and match.classification.supports_candidate
        and match.classification.expires_at
        and match.classification.expires_at > now
    ):
        return []
    if any(
        m.mode != match.mode
        or m.settlement_asset != "USD"
        or (m.instrument_constraints and m.instrument_constraints.unit_payout != 1)
        or m.ingestion_issues
        or m.status != "open"
        or m.closes_at <= now
        or book_issue(m, books.get(m.id), now, settings.max_quote_age_seconds)
        for m in markets
    ):
        return []
    snapshots = [books[m.id] for m in markets]
    if abs((snapshots[0].effective_at - snapshots[1].effective_at).total_seconds()) > (
        settings.max_quote_skew_seconds
    ):
        return []
    summary = match.qualification or QualificationSummary()
    results = []
    for sides in (("yes", "no"), ("no", "yes")):
        ladders = [getattr(b, side + "_asks") for b, side in zip(snapshots, sides, strict=True)]
        maximum = min(
            settings.max_contracts,
            *(int(sum(level.size for level in ladder)) for ladder in ladders),
        )
        minimum = int(
            max(b.min_order_size for b in snapshots).to_integral_value(rounding=ROUND_CEILING)
        )
        best = None
        for count in range(minimum, maximum + 1):
            quantity = Decimal(count)
            fills = [fill(ladder, quantity) for ladder in ladders]
            if any(f is None for f in fills):
                continue
            cost = sum(f[0] for f in fills)
            # An acquisition lower bound can exclude over-budget candidates even
            # when a venue's additional collateral is unknown.
            if cost > settings.max_capital:
                break
            gross = quantity - cost
            if gross <= 0:
                continue
            fees = capital = net = None
            issues = list(summary.blocked_reasons)
            if context and not context.blocked_reasons and len(context.policies) == 2:
                constraints = [m.instrument_constraints for m in markets]
                if any(
                    c
                    and (
                        quantity % c.quantity_increment
                        or quantity < c.minimum_quantity
                        or any(
                            not valid_price(c, native_price(m, side, level.price))
                            for level in ladder
                        )
                    )
                    for c, m, side, ladder in zip(constraints, markets, sides, ladders, strict=True)
                ):
                    continue
                bounds = [
                    fee_bound(p, consume(ladder, quantity), now)
                    for p, ladder in zip(context.policies, ladders, strict=True)
                ]
                if all(b is not None for b in bounds):
                    fees = sum(bounds)
                    reserve = (cost * settings.slippage_bps / Decimal(10000)).quantize(
                        Decimal("0.01"), rounding=ROUND_CEILING
                    )
                    capital = sum(
                        quantity * (1 if is_short(m, side) else f[1])
                        for m, side, f in zip(markets, sides, fills, strict=True)
                    )
                    capital += fees + reserve
                    if capital > settings.max_capital:
                        break
                    net = gross - fees - reserve
            else:
                issues.extend(context.blocked_reasons if context else ("public_costs_unavailable",))
            item = PotentialOpportunity(
                id=digest(
                    [match.id, [b.id for b in snapshots], sides, count, summary.assessment_id]
                ),
                match_id=match.id,
                mode=match.mode,
                feed_origin=match.feed_origin,
                evaluated_at=now,
                valid_until=min(
                    *(
                        b.effective_at + timedelta(seconds=settings.max_quote_age_seconds)
                        for b in snapshots
                    ),
                    *(m.closes_at for m in markets),
                ),
                market_ids=tuple(m.id for m in markets),
                book_ids=tuple(b.id for b in snapshots),
                terms_hashes=tuple(m.terms_hash for m in markets),
                fee_revision_ids=context.fee_revision_ids if context and fees is not None else (),
                outcomes=sides,
                quantity=quantity,
                acquisition_cost=cost,
                ordinary_payout_assumption=quantity,
                gross_spread=gross,
                fee_bound=fees,
                estimated_net_spread=net,
                capital_required=capital,
                qualification=summary,
                unresolved_reasons=tuple(sorted(set(issues or ("qualification_pending",)))),
                assumptions=tuple(
                    dict.fromkeys(
                        (*POTENTIAL_ASSUMPTIONS, *(context.assumptions if context else ()))
                    )
                ),
            )
            score = net if net is not None else gross
            if best is None or score > (
                best.estimated_net_spread
                if best.estimated_net_spread is not None
                else best.gross_spread
            ):
                best = item
        if best:
            results.append(best)
    return results


async def publish(database, mode, match_ids, items):
    async with database.sessions.begin() as session:
        await session.execute(
            update(PotentialRecord)
            .where(PotentialRecord.mode == mode, PotentialRecord.match_id.in_(match_ids))
            .values(active=False)
        )
        for item in items:
            await session.merge(
                PotentialRecord(
                    id=item.id,
                    mode=mode,
                    match_id=item.match_id,
                    evaluated_at=item.evaluated_at,
                    valid_until=item.valid_until,
                    gross_spread=item.gross_spread,
                    capital_required=item.capital_required,
                    active=True,
                    payload=item.model_dump(mode="json"),
                )
            )


async def query(repository, settings, *, limit=100, offset=0, item_id=None, history=False):
    from arbbot.matching.classification import summary as advice_summary
    from arbbot.qualification.service import refresh_match
    from arbbot.storage.models import ClassificationJobRecord

    health = await repository.health(settings.mode, settings.health_timeout_seconds)
    healthy = {
        f["book_id"]
        for h in health
        if h["status"] != "stale"
        and h.get("discovery_ok")
        and h["venue"] in settings.enabled_venues
        for f in h["market_health"]
        if f["status"] == "healthy" and f["book_id"]
    }
    statement = select(PotentialRecord).where(PotentialRecord.mode == settings.mode)
    if item_id:
        statement = statement.where(PotentialRecord.id == item_id)
    if not history:
        statement = statement.where(
            PotentialRecord.active.is_(True), PotentialRecord.valid_until > utcnow()
        )
        for index in (0, 1):
            statement = statement.where(
                PotentialRecord.payload["book_ids"][index].as_string().in_(healthy)
            )
    results = []
    async with repository.database.sessions() as session:
        rows = await session.stream_scalars(
            statement.order_by(
                PotentialRecord.gross_spread.desc(), PotentialRecord.id
            ).execution_options(yield_per=200)
        )
        async for row in rows:
            item = PotentialOpportunity.model_validate(row.payload)
            if history:
                results.append(item)
                if len(results) >= offset + limit:
                    break
                continue
            match_row = await session.get(MatchRecord, item.match_id)
            if not match_row or not match_row.current:
                continue
            match = await refresh_match(session, Match.model_validate(match_row.payload))
            if match.status == "rejected" or (match.qualification.status == "incompatible"):
                continue
            if not (match.comparison and match.comparison.same_event):
                job = await session.get(ClassificationJobRecord, f"{settings.mode}:{match.id}")
                advice = await advice_summary(session, job) if job else None
                if not advice or not advice.supports_candidate:
                    continue
            valid = True
            markets = []
            for mid, bid, terms in zip(
                item.market_ids, item.book_ids, item.terms_hashes, strict=True
            ):
                market_row = await session.get(MarketRecord, f"{settings.mode}:{mid}")
                if not market_row or market_row.latest_book_id != bid:
                    valid = False
                    break
                market = restore(Market, market_row.payload)
                markets.append(market)
                if (
                    market.terms_hash != terms
                    or market.status != "open"
                    or market.closes_at <= utcnow()
                    or market.ingestion_issues
                ):
                    valid = False
                    break
            if valid:
                from arbbot.execution.repository import ExecutionRepository

                context = await ExecutionRepository(repository.database).public_context(
                    session, settings.mode, markets
                )
                if match.qualification.status == "qualified" and not context.blocked_reasons:
                    continue
                changes = {
                    "qualification": match.qualification,
                    "assumptions": tuple(
                        dict.fromkeys((*POTENTIAL_ASSUMPTIONS, *context.assumptions))
                    ),
                    "unresolved_reasons": tuple(
                        sorted(
                            set((*match.qualification.blocked_reasons, *context.blocked_reasons))
                        )
                    )
                    or ("qualification_pending",),
                }
                if context.blocked_reasons or context.fee_revision_ids != item.fee_revision_ids:
                    changes.update(fee_bound=None, estimated_net_spread=None, capital_required=None)
                results.append(item.model_copy(update=changes))
                if len(results) >= offset + limit:
                    break
        await rows.close()
    return results[offset : offset + limit]
