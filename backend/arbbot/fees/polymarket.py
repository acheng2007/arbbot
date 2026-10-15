"""Market-specific linear Polymarket fee bounds from observed Gamma metadata."""

from datetime import timedelta
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Literal
from urllib.parse import quote

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from arbbot.domain import Mode, digest
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.fees.models import Amount, FeeCharge, FeeModel, FeeQuote, FeeUnavailable, Price

QUANTUM = Decimal("0.00001")
POLICY_VERSION = "polymarket-linear-ceiling/2026-09-27"


class FeeSchedule(FeeModel):
    rate: Price
    exponent: Amount = Field(le=100)
    taker_only: StrictBool


class PolymarketFeePolicy(FeeModel):
    market_id: str = Field(pattern=r"^polymarket:[0-9]+$")
    mode: Mode
    settlement_asset: Literal["pUSD"] = "pUSD"
    supported_instrument: StrictBool
    fees_enabled: StrictBool | None
    schedule: FeeSchedule | None
    observed_at: AwareDatetime
    effective_at: AwareDatetime
    expires_at: AwareDatetime
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def bounded_lifetime(self):
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=15):
            raise ValueError("Fee metadata lifetime must be positive and at most 15 minutes")
        if self.effective_at >= self.expires_at:
            raise ValueError("Fee policy must become effective before expiry")
        return self


def policy_from_payload(payload, *, market_id, mode, observed_at, ttl_seconds=300):
    """Use ExchangeHTTP JSON (numeric tokens preserved as strings), not binary floats."""
    if market_id != "polymarket:" + str(payload.get("id", "")):
        raise ValueError("Fee metadata belongs to a different market")
    data = payload.get("feeSchedule")
    schedule = None
    if data is not None:
        if not isinstance(data, dict):
            raise ValueError("Malformed fee schedule")
        schedule = FeeSchedule(
            rate=data.get("rate"), exponent=data.get("exponent"), taker_only=data.get("takerOnly")
        )
    return PolymarketFeePolicy(
        market_id=market_id,
        mode=mode,
        supported_instrument=PolymarketAdapter.supported(payload),
        fees_enabled=payload.get("feesEnabled"),
        schedule=schedule,
        observed_at=observed_at,
        effective_at=observed_at,
        expires_at=observed_at + timedelta(seconds=ttl_seconds),
        payload_digest=digest(payload),
    )


class PolymarketFeeProvider:
    def __init__(self, policy: PolymarketFeePolicy | None):
        self.policy = PolymarketFeePolicy.model_validate(policy) if policy is not None else None

    async def quote(self, request, *, as_of):
        policy = self.policy

        def unavailable(reason):
            return FeeUnavailable(request=request, as_of=as_of, reason=reason)

        if policy is None:
            return unavailable("missing_policy")
        if (
            request.venue != "polymarket"
            or request.market_id != policy.market_id
            or request.mode != policy.mode
            or request.settlement_asset != policy.settlement_asset
            or not policy.supported_instrument
        ):
            return unavailable("unsupported")
        if policy.observed_at > as_of or policy.effective_at > as_of:
            return unavailable("not_yet_effective")
        if policy.expires_at <= as_of:
            return unavailable("stale")
        if policy.fees_enabled is None:
            return unavailable("missing_policy")
        schedule = policy.schedule
        zero_reason = None
        if not policy.fees_enabled:
            if schedule and schedule.rate != 0:
                return unavailable("unsupported")
            rate = Decimal(0)
            zero_reason = "Observed market metadata explicitly disables fees"
        else:
            if schedule is None:
                return unavailable("missing_policy")
            if schedule.exponent != 1 or not schedule.taker_only:
                return unavailable("unsupported")
            rate = schedule.rate if request.liquidity == "taker" else Decimal(0)
            if request.liquidity == "maker":
                zero_reason = "Observed schedule charges takers only; no rebate is assumed"
            elif rate == 0:
                zero_reason = "Observed market schedule has an explicit zero rate"
        charges = []
        with localcontext() as context:
            context.prec = 128
            for index, fill in enumerate(request.fills):
                # Round upward at each supplied fill boundary. This is a fee
                # bound, not an assertion about the exchange's tie-breaking rule.
                amount = (fill.quantity * rate * fill.price * (1 - fill.price)).quantize(
                    QUANTUM, rounding=ROUND_CEILING
                )
                charges.append(
                    FeeCharge(
                        name="polymarket_fee_bound",
                        basis="price_dependent",
                        scope="fill",
                        fill_index=index,
                        amount=amount,
                        rounding_increment=QUANTUM,
                    )
                )
        return FeeQuote(
            request=request,
            as_of=as_of,
            source="https://gamma-api.polymarket.com/markets/"
            + quote(policy.market_id.split(":", 1)[1], safe=""),
            policy_version=POLICY_VERSION + ":" + policy.payload_digest,
            observed_at=policy.observed_at,
            effective_at=policy.effective_at,
            expires_at=policy.expires_at,
            charges=tuple(charges),
            zero_fee_reason=zero_reason
            or (
                "All supplied prices have zero fee under the observed curve"
                if not any(c.amount for c in charges)
                else None
            ),
        )
