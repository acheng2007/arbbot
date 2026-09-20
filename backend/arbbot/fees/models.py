from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from arbbot.domain import Mode, Outcome, Venue


def exact_input(value):
    if isinstance(value, (float, bool)):
        raise ValueError("Financial values require decimal strings, Decimal, or integers")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(exact_input),
    Field(
        ge=0,
        allow_inf_nan=False,
        max_digits=30,
        decimal_places=12,
    ),
]
PositiveAmount = Annotated[Amount, Field(gt=0)]
Price = Annotated[Amount, Field(le=1)]


class FeeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class Fill(FeeModel):
    price: Price
    quantity: PositiveAmount


class FeeRequest(FeeModel):
    schema_version: Literal[1] = 1
    mode: Mode
    venue: Venue
    market_id: str = Field(min_length=1, max_length=512)
    outcome: Outcome
    side: Literal["buy", "sell"]
    liquidity: Literal["maker", "taker"]
    settlement_asset: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,15}$")
    quantity: PositiveAmount
    fills: tuple[Fill, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_fills(self):
        if not self.market_id.startswith(self.venue + ":"):
            raise ValueError("Market identifier must belong to the requested venue")
        with localcontext() as context:
            context.prec = 80
            if sum((fill.quantity for fill in self.fills), Decimal(0)) != self.quantity:
                raise ValueError("Fill quantities must equal the requested quantity")
        return self


class FeeCharge(FeeModel):
    """Adapter-calculated charge before rounding, in the request's settlement asset."""

    name: str = Field(min_length=1, max_length=128)
    basis: Literal["fixed", "quantity", "price_dependent"]
    scope: Literal["order", "fill"]
    fill_index: int | None = Field(default=None, ge=0)
    amount: Amount
    rounding_increment: PositiveAmount

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.scope == "fill") != (self.fill_index is not None):
            raise ValueError("Only fill-scoped charges require a fill index")
        return self

    @computed_field
    @property
    def rounded_amount(self) -> Decimal:
        with localcontext() as context:
            context.prec = 80
            return (self.amount / self.rounding_increment).to_integral_value(
                rounding=ROUND_CEILING
            ) * self.rounding_increment


class FeeQuote(FeeModel):
    schema_version: Literal[1] = 1
    status: Literal["available"] = "available"
    request: FeeRequest
    as_of: AwareDatetime
    source: str = Field(min_length=1, max_length=2048)
    policy_version: str = Field(min_length=1, max_length=256)
    observed_at: AwareDatetime
    effective_at: AwareDatetime
    expires_at: AwareDatetime
    charges: tuple[FeeCharge, ...] = Field(min_length=1, max_length=3000)
    zero_fee_reason: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_quote(self):
        if not self.source.strip() or not self.policy_version.strip():
            raise ValueError("Fee quotes require source and policy version")
        if self.observed_at > self.as_of or not self.effective_at <= self.as_of < self.expires_at:
            raise ValueError("Fee information must be observed, effective, and unexpired")
        if len({(c.name, c.fill_index) for c in self.charges}) != len(self.charges):
            raise ValueError("Duplicate fee charge")
        if any(
            c.fill_index is not None and c.fill_index >= len(self.request.fills)
            for c in self.charges
        ):
            raise ValueError("Fee charge refers to an absent fill")
        if self.total == 0 and not (self.zero_fee_reason and self.zero_fee_reason.strip()):
            raise ValueError("Zero fees require an explicit verified policy reason")
        return self

    @computed_field
    @property
    def total(self) -> Decimal:
        with localcontext() as context:
            context.prec = 80
            return sum((charge.rounded_amount for charge in self.charges), Decimal(0))


class FeeUnavailable(FeeModel):
    schema_version: Literal[1] = 1
    status: Literal["unavailable"] = "unavailable"
    request: FeeRequest
    as_of: AwareDatetime
    reason: Literal[
        "unsupported",
        "stale",
        "not_yet_effective",
        "missing_policy",
        "provider_error",
        "invalid_quote",
    ]


FeeResult = Annotated[FeeQuote | FeeUnavailable, Field(discriminator="status")]
