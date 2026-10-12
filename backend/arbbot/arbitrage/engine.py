from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from arbbot.config import Settings
from arbbot.domain import (
    Book,
    Evaluation,
    Leg,
    Market,
    Match,
    Opportunity,
    SignedCalculation,
    digest,
)
from arbbot.fees.executable import fee_bound
from arbbot.fees.models import Fill
from arbbot.matching.contracts import compare_contracts
from arbbot.matching.settlement import settlement_issues
from arbbot.quality import book_issue

ZERO = Decimal(0)
CENT = Decimal("0.01")


def fill(levels, quantity: Decimal) -> tuple[Decimal, Decimal] | None:
    remaining, cost, limit = quantity, ZERO, ZERO
    for level in levels:
        taken = min(level.size, remaining)
        cost += taken * level.price
        remaining -= taken
        limit = level.price
        if remaining == 0:
            return cost, limit
    return None


def valid_price(constraints, price):
    if constraints.price_ranges:
        return any(
            b.start <= price <= b.end and (price - b.start) % b.step == 0
            for b in constraints.price_ranges
        )
    return price % constraints.price_increment == 0


def consume(levels, quantity):
    remaining, fills = quantity, []
    for level in levels:
        taken = min(level.size, remaining)
        fills.append(Fill(price=level.price, quantity=taken))
        remaining -= taken
        if remaining == 0:
            return tuple(fills)
    return ()


def evaluate(
    match: Match,
    left: Market,
    right: Market,
    books: dict[str, Book],
    settings: Settings,
    now: datetime,
    execution=None,
) -> Evaluation:
    reasons = []
    review = match.review
    if match.status != "verified" or review is None or review.status != "verified":
        reasons.append("settlement_equivalence_unverified")
    elif (
        review.expires_at <= now
        or review.left_terms_hash != left.terms_hash
        or review.right_terms_hash != right.terms_hash
    ):
        reasons.append("review_invalid_or_expired")
    if match.mode == "live":
        if any(m.venue == "polymarket_us" for m in (left, right)):
            if execution is None:
                reasons.extend(
                    (
                        "installation_access_unknown",
                        "source_applicability_unverified",
                        "fee_policy_unavailable",
                    )
                )
            else:
                reasons.extend(execution.blocked_reasons)
                if execution.valid_until is None or execution.valid_until <= now:
                    reasons.append("execution_configuration_expired")
                if len(execution.policies) == 2 and any(
                    p.market_id != m.id or p.terms_hash != m.terms_hash
                    for p, m in zip(execution.policies, (left, right), strict=True)
                ):
                    reasons.append("fee_policy_identity_mismatch")
                if len(execution.policies) != 2:
                    reasons.append("fee_policy_unavailable")
        if any(m.venue == "polymarket_us" for m in (left, right)):
            for market in (left, right):
                if market.instrument_constraints is None or market.execution_semantics is None:
                    reasons.append(f"native_constraints_unverified:{market.id}")
                if market.instrument_constraints and market.instrument_constraints.unit_payout != 1:
                    reasons.append(f"unsupported_unit_payout:{market.id}")
                semantics = market.execution_semantics
                if (
                    market.venue == "polymarket_us"
                    and semantics
                    and (
                        semantics.yes_action != "buy_instrument"
                        or semantics.no_action != "short_instrument"
                        or not semantics.no_native_price_is_complement
                        or semantics.gross_short_collateral_per_contract != 1
                    )
                ):
                    reasons.append(f"unsupported_native_exposure:{market.id}")
                if market.settlement_asset != "USD":
                    reasons.append(f"unsupported_settlement_asset:{market.id}")
            if review and any(
                p.cost_fx != 1 or p.payout_fx != 1 for p in (review.left_costs, review.right_costs)
            ):
                reasons.append("usd_conversion_policy_invalid")
        comparison = compare_contracts(
            left,
            right,
            match.comparison.left if match.comparison else None,
            match.comparison.right if match.comparison else None,
        )
        reasons.extend(settlement_issues(review, comparison.left, comparison.right))
        if (
            comparison.status != "compatible"
            or review is None
            or (review.left_definition_hash, review.right_definition_hash)
            != (comparison.left_hash, comparison.right_hash)
        ):
            reasons.append("structured_equivalence_unverified")
    if left.mode != right.mode or match.mode != left.mode:
        reasons.append("mixed_data_modes")
    for market in (left, right):
        if market.ingestion_issues:
            reasons.append(f"instrument_data_invalid:{market.id}")
        if market.status != "open" or market.closes_at <= now:
            reasons.append(f"market_closed:{market.id}")
        issue = book_issue(market, books.get(market.id), now, settings.max_quote_age_seconds)
        if issue:
            reasons.append(f"{issue}:{market.id}")
    if not reasons:
        skew = abs((books[left.id].effective_at - books[right.id].effective_at).total_seconds())
        if skew > settings.max_quote_skew_seconds:
            reasons.append("quotes_not_synchronized")
    if reasons:
        return Evaluation(
            match_id=match.id,
            mode=match.mode,
            evaluated_at=now,
            blocked_reasons=tuple(reasons),
            opportunities=(),
            status="invalid"
            if any(
                r.startswith(
                    (
                        "mixed_data",
                        "book_identity",
                        "book_mode",
                        "book_from_future",
                        "book_stale",
                        "instrument_data_invalid",
                    )
                )
                for r in reasons
            )
            else "blocked",
        )

    assert review is not None
    a, b = books[left.id], books[right.id]
    policies = review.left_costs, review.right_costs
    opportunities = []
    best_calculation = None
    unavailable_fees = False
    live_us = match.mode == "live" and any(m.venue == "polymarket_us" for m in (left, right))
    for sides in (("yes", "no"), ("no", "yes")):
        if live_us and any(
            side == "no"
            and market.venue == "polymarket_us"
            and market.id not in execution.short_allowed_market_ids
            for market, side in zip((left, right), sides, strict=True)
        ):
            continue
        ladders = (getattr(a, f"{sides[0]}_asks"), getattr(b, f"{sides[1]}_asks"))
        maximum = min(
            settings.max_contracts,
            *(int(sum((level.size for level in ls), ZERO)) for ls in ladders),
        )
        minimum = int(
            max(
                a.min_order_size, b.min_order_size, *(p.min_order_size for p in policies)
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        best = None
        # Whole-contract sizing is deliberately conservative across both venues.
        # Evaluate each size within the configured bound, including depth transitions.
        for count in range(minimum, maximum + 1):
            quantity = Decimal(count)
            fills = [fill(ladder, quantity) for ladder in ladders]
            if any(f is None for f in fills):
                break
            if any(f[0] < p.min_notional for f, p in zip(fills, policies, strict=True)):
                continue
            constraints = [m.instrument_constraints for m in (left, right)]
            if live_us and any(c is None for c in constraints):
                continue
            if any(
                c
                and (
                    quantity % c.quantity_increment
                    or quantity < c.minimum_quantity
                    or any(
                        not valid_price(
                            c,
                            1 - level.price
                            if market.venue == "polymarket_us" and side == "no"
                            else level.price,
                        )
                        for level in ladder
                    )
                )
                for c, ladder, market, side in zip(
                    constraints, ladders, (left, right), sides, strict=True
                )
            ):
                continue
            costs = [f[0] * p.cost_fx for f, p in zip(fills, policies, strict=True)]
            fees = [
                ((p.fee_per_contract * quantity + p.fixed_fee) * p.cost_fx).quantize(
                    CENT, rounding=ROUND_CEILING
                )
                for p in policies
            ]
            if live_us:
                fees = [
                    fee_bound(p, consume(ladder, quantity), now)
                    for p, ladder in zip(execution.policies, ladders, strict=True)
                ]
                if any(fee is None for fee in fees):
                    unavailable_fees = True
                    continue
            reserve = (sum(costs) * settings.slippage_bps / Decimal(10000)).quantize(
                CENT, rounding=ROUND_CEILING
            )
            outlay = sum(costs) + sum(fees) + reserve
            # A venue may reserve the whole order at its limit price, even when
            # displayed depth implies a lower volume-weighted acquisition cost.
            capital = (
                sum(
                    quantity
                    * (Decimal(1) if market.venue == "polymarket_us" and side == "no" else f[1])
                    * p.cost_fx
                    for market, side, f, p in zip(
                        (left, right), sides, fills, policies, strict=True
                    )
                )
                + sum(fees)
                + reserve
            )
            if capital > settings.max_capital:
                break
            payouts = {}
            for scenario in review.scenarios:
                payouts[scenario.name] = quantity * sum(
                    scenario.payout(venue_side, side) * policy.payout_fx
                    for venue_side, side, policy in zip(
                        ("left", "right"), sides, policies, strict=True
                    )
                )
            payout = min(payouts.values())
            profit = payout - outlay
            if capital <= 0:
                continue
            legs = tuple(
                Leg(
                    market_id=market.id,
                    outcome=side,
                    quantity=quantity,
                    limit_price=f[1],
                    book_id=book.id,
                    quote_at=book.effective_at,
                    source_at=book.source_at,
                    received_at=book.received_at,
                    source_timestamp_available=book.source_at is not None,
                    native_cost=f[0],
                    cost_usd=cost,
                    fee_bound_usd=fee,
                    native_action=(
                        market.execution_semantics.yes_action
                        if side == "yes"
                        else market.execution_semantics.no_action
                    )
                    if market.execution_semantics
                    else None,
                    native_price=1 - f[1]
                    if market.venue == "polymarket_us" and side == "no"
                    else f[1],
                    short_proceeds=quantity - f[0]
                    if market.venue == "polymarket_us" and side == "no"
                    else ZERO,
                    gross_collateral=quantity
                    if market.venue == "polymarket_us" and side == "no"
                    else ZERO,
                    net_buying_power=quantity * f[1] + fee,
                    fee_policy_id=execution.fee_revision_ids[index] if live_us else None,
                )
                for index, (market, side, book, f, cost, fee) in enumerate(
                    zip((left, right), sides, (a, b), fills, costs, fees, strict=True)
                )
            )
            signed = SignedCalculation(
                quantity=quantity,
                legs=legs,
                capital_required=capital,
                estimated_outlay=outlay,
                fee_bound=sum(fees),
                slippage_reserve=reserve,
                minimum_payout=payout,
                net_profit=profit,
                scenario_payouts=payouts,
            )
            if best_calculation is None or profit > best_calculation.net_profit:
                best_calculation = signed
            if profit < settings.min_profit or (best is not None and profit <= best.net_profit):
                continue
            best = Opportunity(
                id=digest(
                    [
                        match.id,
                        a.id,
                        b.id,
                        sides,
                        count,
                        now.isoformat(),
                        review.model_dump(mode="json"),
                    ]
                ),
                match_id=match.id,
                review_revision_id=match.review_revision_id,
                access_revision_id=execution.access_revision_id if live_us else None,
                applicability_revision_ids=execution.applicability_revision_ids if live_us else (),
                fee_revision_ids=execution.fee_revision_ids if live_us else (),
                mode=match.mode,
                feed_origin=match.feed_origin,
                classification="simulation"
                if match.mode == "simulation" or match.feed_origin != "exchange"
                else "quote_supported_estimate",
                evaluated_at=now,
                quote_skew_seconds=abs((a.effective_at - b.effective_at).total_seconds()),
                valid_until=min(
                    a.effective_at + timedelta(seconds=settings.max_quote_age_seconds),
                    b.effective_at + timedelta(seconds=settings.max_quote_age_seconds),
                    left.closes_at,
                    right.closes_at,
                    review.expires_at,
                    execution.valid_until if live_us else review.expires_at,
                ),
                quantity=quantity,
                legs=legs,
                capital_required=capital,
                estimated_outlay=outlay,
                fee_bound=sum(fees),
                slippage_reserve=reserve,
                minimum_payout=payout,
                net_profit=profit,
                return_on_capital=profit / capital,
                scenario_payouts=payouts,
                review=review,
                comparison=match.comparison,
                assumptions=(
                    "Both legs fill in full; execution is not atomic.",
                    "Reviewed installation access must remain effective; prefunded balances "
                    "and account limits are unverified."
                    if live_us
                    else "Venue access, prefunded balances, and account limits are unverified.",
                    "Reviewed fee bounds, conversion bounds, and settlement scenarios hold.",
                    "Whole-contract sizes only; optimum is within configured size/capital bounds.",
                    "Quotes may change; estimated profit is not guaranteed.",
                ),
            )
        if best:
            opportunities.append(best)
    return Evaluation(
        match_id=match.id,
        mode=match.mode,
        evaluated_at=now,
        blocked_reasons=()
        if opportunities
        else (
            "fee_policy_execution_granularity_unavailable"
            if unavailable_fees
            else "no_profitable_size_within_constraints",
        ),
        status="profitable" if opportunities else "unprofitable" if best_calculation else "blocked",
        best_calculation=best_calculation,
        access_revision_id=execution.access_revision_id if live_us else None,
        fee_revision_ids=execution.fee_revision_ids if live_us else (),
        opportunities=tuple(opportunities),
    )
