from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from arbbot.config import Settings
from arbbot.domain import Book, Evaluation, Leg, Market, Match, Opportunity, digest
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


def evaluate(
    match: Match,
    left: Market,
    right: Market,
    books: dict[str, Book],
    settings: Settings,
    now: datetime,
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
        )

    assert review is not None
    a, b = books[left.id], books[right.id]
    policies = review.left_costs, review.right_costs
    opportunities = []
    for sides in (("yes", "no"), ("no", "yes")):
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
            costs = [f[0] * p.cost_fx for f, p in zip(fills, policies, strict=True)]
            fees = [
                ((p.fee_per_contract * quantity + p.fixed_fee) * p.cost_fx).quantize(
                    CENT, rounding=ROUND_CEILING
                )
                for p in policies
            ]
            reserve = (sum(costs) * settings.slippage_bps / Decimal(10000)).quantize(
                CENT, rounding=ROUND_CEILING
            )
            outlay = sum(costs) + sum(fees) + reserve
            # A venue may reserve the whole order at its limit price, even when
            # displayed depth implies a lower volume-weighted acquisition cost.
            capital = (
                sum(quantity * f[1] * p.cost_fx for f, p in zip(fills, policies, strict=True))
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
            if capital <= 0 or profit < settings.min_profit:
                continue
            if best is not None and profit <= best.net_profit:
                continue
            legs = tuple(
                Leg(
                    market_id=market.id,
                    outcome=side,
                    quantity=quantity,
                    limit_price=f[1],
                    book_id=book.id,
                    quote_at=book.effective_at,
                    source_timestamp_available=book.source_at is not None,
                    native_cost=f[0],
                    cost_usd=cost,
                    fee_bound_usd=fee,
                )
                for market, side, book, f, cost, fee in zip(
                    (left, right), sides, (a, b), fills, costs, fees, strict=True
                )
            )
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
                mode=match.mode,
                classification="simulation"
                if match.mode == "simulation"
                else "quote_supported_estimate",
                evaluated_at=now,
                valid_until=min(
                    a.effective_at + timedelta(seconds=settings.max_quote_age_seconds),
                    b.effective_at + timedelta(seconds=settings.max_quote_age_seconds),
                    left.closes_at,
                    right.closes_at,
                    review.expires_at,
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
                    "Venue access, prefunded balances, and account limits are unverified.",
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
        blocked_reasons=() if opportunities else ("no_profitable_size_within_constraints",),
        opportunities=tuple(opportunities),
    )
