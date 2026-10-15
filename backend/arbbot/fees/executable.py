"""Pure conservative order bounds. Depth levels are not individual executions."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, localcontext


def _binary_bound(policy, fills, now):
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


@dataclass(frozen=True)
class FeeFormula:
    validate: Callable
    bound: Callable


def _validate_binary(policy):
    # Built-in policy constraints are checked by ExecutableFeePolicy.
    return None


FORMULAS = {
    "kalshi_quadratic": FeeFormula(_validate_binary, _binary_bound),
    "us_standard": FeeFormula(_validate_binary, _binary_bound),
}


def fee_bound(policy, fills, now):
    provider = FORMULAS.get(policy.formula)
    if (
        not provider
        or not policy.effective_at <= now < policy.expires_at
        or policy.observed_at > now
    ):
        return None
    value = provider.bound(policy, fills, now)
    if value is None or not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        return None
    return value
