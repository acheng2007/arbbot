"""Pure conservative order bounds. Depth levels are not individual executions."""

from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, localcontext


def fee_bound(policy, fills, now):
    if not policy.effective_at <= now < policy.expires_at or policy.observed_at > now:
        return None
    with localcontext() as context:
        context.prec = 80
        exact = sum(
            (policy.coefficient * f.quantity * f.price * (1 - f.price) for f in fills), Decimal(0)
        )
        if policy.formula == "us_standard":
            # Official cumulative cap applies even when aggregated levels fragment.
            return exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        increment = policy.minimum_execution_quantity
        precision = policy.balance_precision
        if (
            increment is None
            or precision is None
            or any(f.quantity % increment or f.price % Decimal("0.0001") for f in fills)
        ):
            return None
        quantity = sum((f.quantity for f in fills), Decimal(0))
        executions = quantity / increment
        # Each execution rounds model fees up by <1 microdollar, and its
        # balance adjustment is <precision. Accumulator rebates only reduce
        # charges, but cannot always exhaust the accumulator due to the cap
        # prohibiting negative net fill fees. This bound does not assume that
        # the order ends with a residual accumulator below one precision unit.
        bound = exact + executions * (Decimal("0.000001") + Decimal(precision))
        return bound.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
