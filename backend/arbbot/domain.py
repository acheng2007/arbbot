"""Validated exchange-independent data. Decimal values serialize as strings."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from arbbot.matching.classification_models import ClassificationSummary
from arbbot.matching.contracts import Comparison
from arbbot.qualification.summary import QualificationSummary

NonNegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Probability = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]


def registered_venue(value):
    from arbbot.venues import VENUES

    if value not in VENUES:
        raise ValueError("Venue must be registered")
    return value


Venue = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$"), AfterValidator(registered_venue)]
Mode = Literal["simulation", "live"]
Outcome = Literal["yes", "no"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def discard_derived_fields(cls, value):
        if isinstance(value, dict):
            return {k: v for k, v in value.items() if k not in cls.model_computed_fields}
        return value


class PriceBand(Model):
    start: Probability
    end: Probability
    step: Positive

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("Price band must have positive width")
        return self


class InstrumentConstraints(Model):
    price_increment: Positive
    price_ranges: tuple[PriceBand, ...] = ()
    quantity_increment: Positive
    minimum_quantity: Positive
    unit_payout: Positive = Decimal("1")
    payout_currency: Literal["USD"] = "USD"
    payout_evidence: str = Field(min_length=10)


class ExecutionSemantics(Model):
    yes_action: Literal["buy_yes", "buy_instrument"]
    no_action: Literal["buy_no", "short_instrument"]
    no_native_price_is_complement: bool = False
    gross_short_collateral_per_contract: NonNegative | None = None


class Market(Model):
    ingestion_issues: tuple[str, ...] = ()
    source_revision: int = Field(default=0, ge=0)
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"] = "exchange"
    id: str
    venue: Venue
    external_id: str
    mode: Mode
    title: str = Field(min_length=1)
    rules: str
    closes_at: AwareDatetime
    status: Literal["open", "closed"]
    settlement_asset: str
    category: str | None = None
    instrument_constraints: InstrumentConstraints | None = None
    execution_semantics: ExecutionSemantics | None = None
    tokens: dict[Outcome, str] = {}
    # Semantic metadata only; changing this invalidates settlement review.
    settlement_details: dict = {}
    raw: dict
    observed_at: AwareDatetime

    @computed_field
    @property
    def category_group(self) -> str:
        from arbbot.discovery.categories import category_group

        return category_group(self.category)

    @computed_field
    @property
    def terms_hash(self) -> str:
        return digest(
            {
                "title": self.title,
                "rules": self.rules,
                "closes_at": self.closes_at.isoformat(),
                "asset": self.settlement_asset,
                "tokens": self.tokens,
                **(
                    {
                        "instrument_constraints": self.instrument_constraints.model_dump(
                            mode="json",
                            exclude={"price_ranges"}
                            if not self.instrument_constraints.price_ranges
                            else set(),
                        )
                    }
                    if self.instrument_constraints
                    else {}
                ),
                **(
                    {"execution_semantics": self.execution_semantics.model_dump(mode="json")}
                    if self.execution_semantics
                    else {}
                ),
                "settlement_details": self.settlement_details,
            }
        )


class MarketSummary(Model):
    counterpart_count: int = 0
    assessment_state: Literal["pending", "assessed", "unavailable"] = "pending"
    ingestion_issues: tuple[str, ...] = ()
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"] = "exchange"
    id: str
    venue: Venue
    external_id: str
    mode: Mode
    title: str
    closes_at: AwareDatetime
    status: Literal["open", "closed"]
    settlement_asset: str
    category: str | None = None
    observed_at: AwareDatetime

    @computed_field
    @property
    def category_group(self) -> str:
        from arbbot.discovery.categories import category_group

        return category_group(self.category)


class Level(Model):
    price: Probability
    size: Positive


class Book(Model):
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"] = "exchange"
    market_id: str
    mode: Mode
    yes_asks: tuple[Level, ...]
    no_asks: tuple[Level, ...]
    min_order_size: Positive = Decimal("1")
    source_at: AwareDatetime | None = None
    received_at: AwareDatetime
    raw: dict

    @model_validator(mode="after")
    def sorted_levels(self):
        for levels in (self.yes_asks, self.no_asks):
            if list(levels) != sorted(levels, key=lambda level: level.price):
                raise ValueError("Ask levels must be sorted by increasing price")
            if len({level.price for level in levels}) != len(levels):
                raise ValueError("Duplicate price levels must be aggregated")
        return self

    @property
    def effective_at(self) -> datetime:
        return min(self.source_at, self.received_at) if self.source_at else self.received_at

    @property
    def id(self) -> str:
        return digest(
            self.model_dump(
                mode="json", exclude={"feed_origin"} if self.feed_origin == "exchange" else set()
            )
        )


class MarketHealth(Model):
    market_id: str
    status: Literal["healthy", "stale", "error", "closed"]
    checked_at: AwareDatetime
    book_id: str | None = None
    quote_at: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    error: str | None = None


class CostPolicy(Model):
    # Legacy conservative envelope; automatic estimates require separate public fee policies.
    fee_per_contract: NonNegative
    fixed_fee: NonNegative
    min_order_size: Positive
    min_notional: NonNegative
    cost_fx: Positive
    payout_fx: Positive
    evidence: str = Field(min_length=10)

    @model_validator(mode="after")
    def conservative_fx(self):
        if self.payout_fx > self.cost_fx:
            raise ValueError("Payout conversion floor cannot exceed acquisition conversion ceiling")
        return self


class Scenario(Model):
    name: str = Field(min_length=1)
    left_yes: Probability
    right_yes: Probability
    # Missing NO values retain legacy simulation/file readability. Live reviews
    # must explicitly describe both purchased outcomes at each venue.
    left_no: Probability | None = None
    right_no: Probability | None = None

    @model_validator(mode="after")
    def complementary_payouts(self):
        if (self.left_no is None) != (self.right_no is None):
            raise ValueError("Explicit settlement requires NO payouts for both venues")
        if self.left_no is not None and (
            self.left_yes + self.left_no != Decimal(1)
            or self.right_yes + self.right_no != Decimal(1)
        ):
            raise ValueError("Non-complementary payouts and variable refunds are unsupported")
        return self

    def payout(self, venue_side: Literal["left", "right"], outcome: Literal["yes", "no"]):
        value = getattr(self, f"{venue_side}_{outcome}")
        return value if value is not None else Decimal(1) - getattr(self, f"{venue_side}_yes")


class SettlementMapping(Model):
    side: Literal["left", "right"]
    policy: Literal["cancellation", "fallback", "ambiguous_resolution"]
    condition_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    scenarios: tuple[str, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def unique_scenarios(self):
        if len(set(self.scenarios)) != len(self.scenarios):
            raise ValueError("Scenario references must be unique")
        return self


class JointSettlementCase(Model):
    left_state: str = Field(
        pattern=r"^(normal_yes|normal_no|(?:cancellation|fallback|ambiguous_resolution):[a-z0-9_]{1,64})$"
    )
    right_state: str = Field(
        pattern=r"^(normal_yes|normal_no|(?:cancellation|fallback|ambiguous_resolution):[a-z0-9_]{1,64})$"
    )
    scenario: str | None = Field(default=None, min_length=1)
    exclusion_reason: str | None = Field(default=None, min_length=20)
    left_evidence_policies: tuple[
        Literal["cancellation", "fallback", "ambiguous_resolution"], ...
    ] = ()
    right_evidence_policies: tuple[
        Literal["cancellation", "fallback", "ambiguous_resolution"], ...
    ] = ()

    @model_validator(mode="after")
    def modeled_or_excluded(self):
        if (self.scenario is None) == (self.exclusion_reason is None):
            raise ValueError(
                "Joint settlement must name a scenario or an evidence-backed exclusion"
            )
        if self.exclusion_reason and (
            not self.left_evidence_policies or not self.right_evidence_policies
        ):
            raise ValueError(
                "Exclusion requires current settlement-policy evidence from both venues"
            )
        return self


class SettlementModel(Model):
    """Calculation inputs established by rules, without human approval provenance."""

    left_id: str
    right_id: str
    left_terms_hash: str
    right_terms_hash: str
    left_definition_hash: str
    right_definition_hash: str
    expires_at: AwareDatetime
    scenarios: tuple[Scenario, ...]
    settlement_mappings: tuple[SettlementMapping, ...] = ()
    joint_settlement_cases: tuple[JointSettlementCase, ...] = ()
    left_costs: CostPolicy
    right_costs: CostPolicy


class Review(Model):
    left_id: str
    right_id: str
    left_terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    right_terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    left_definition_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    right_definition_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: Literal["verified", "rejected"]
    reviewer: str = Field(min_length=1)
    rationale: str = Field(min_length=10)
    resolution_sources: str = Field(min_length=10)
    deadlines_and_timezones: str = Field(min_length=10)
    cancellation_and_exceptions: str = Field(min_length=10)
    expires_at: AwareDatetime
    scenarios: tuple[Scenario, ...] = Field(min_length=2)
    settlement_mappings: tuple[SettlementMapping, ...] = Field(default=(), max_length=192)
    joint_settlement_cases: tuple[JointSettlementCase, ...] = Field(default=(), max_length=1024)
    left_costs: CostPolicy
    right_costs: CostPolicy

    @model_validator(mode="after")
    def validate_pair(self):
        if self.left_id == self.right_id:
            raise ValueError("Review must cover two different markets")
        if len({scenario.name for scenario in self.scenarios}) != len(self.scenarios):
            raise ValueError("Scenario names must be unique")
        outcomes = {(s.left_yes, s.right_yes) for s in self.scenarios}
        if not {(Decimal(0), Decimal(0)), (Decimal(1), Decimal(1))}.issubset(outcomes):
            raise ValueError("Aligned binary contracts must cover both ordinary outcomes")
        return self


class Match(Model):
    retrieval_methods: tuple[str, ...] = ()
    historical: bool = False
    qualification: QualificationSummary | None = None
    settlement: SettlementModel | None = None
    classification: ClassificationSummary | None = None
    ai_only: bool = False
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"] = "exchange"
    retrieval_limited: bool = False
    retrieval_limit: int | None = None
    id: str
    mode: Mode
    left_id: str
    right_id: str
    status: Literal["candidate", "verified", "rejected"]
    similarity: float
    reason: str
    review: Review | None = None
    comparison: Comparison | None = None
    review_revision_id: str | None = None

    @computed_field
    @property
    def operator_veto(self) -> bool:
        return (
            bool(
                self.qualification
                and "explicit_operator_veto" in self.qualification.blocked_reasons
            )
            or self.status == "rejected"
        )

    @computed_field
    @property
    def relationship(self) -> Literal["unverified", "verified", "mismatch"]:
        if self.historical:
            return "unverified"
        q = self.qualification
        if q:
            if q.status == "qualified":
                return "verified"
            if q.status == "incompatible" and not self.operator_veto:
                return "mismatch"
            return "unverified"
        # Historical human decisions retain their own provenance and meaning.
        if self.status == "verified":
            return "verified"
        if self.comparison and self.comparison.status == "conflict":
            return "mismatch"
        return "unverified"


class Leg(Model):
    source_at: AwareDatetime | None = None
    received_at: AwareDatetime | None = None
    native_action: Literal["buy_yes", "buy_no", "buy_instrument", "short_instrument"] | None = None
    native_price: Probability | None = None
    short_proceeds: NonNegative = Decimal(0)
    gross_collateral: NonNegative = Decimal(0)
    net_buying_power: NonNegative | None = None
    fee_policy_id: str | None = None
    market_id: str
    outcome: Outcome
    quantity: Positive
    limit_price: Probability
    book_id: str
    quote_at: AwareDatetime
    source_timestamp_available: bool
    native_cost: NonNegative
    cost_usd: NonNegative
    fee_bound_usd: NonNegative


class SignedCalculation(Model):
    quantity: Positive
    legs: tuple[Leg, Leg]
    capital_required: Positive
    estimated_outlay: Positive
    fee_bound: NonNegative
    slippage_reserve: NonNegative
    minimum_payout: NonNegative
    net_profit: Decimal = Field(allow_inf_nan=False)
    scenario_payouts: dict[str, Decimal]


class Opportunity(Model):
    quote_skew_seconds: float | None = Field(default=None, ge=0)
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"] = "exchange"
    access_revision_id: str | None = None
    applicability_revision_ids: tuple[str, ...] = ()
    fee_revision_ids: tuple[str, ...] = ()
    id: str
    match_id: str
    mode: Mode
    classification: Literal["simulation", "quote_supported_estimate"]
    evaluated_at: AwareDatetime
    valid_until: AwareDatetime
    quantity: Positive
    legs: tuple[Leg, Leg]
    capital_required: Positive
    estimated_outlay: Positive | None = None
    fee_bound: NonNegative
    slippage_reserve: NonNegative
    minimum_payout: NonNegative
    net_profit: Positive
    return_on_capital: Positive
    scenario_payouts: dict[str, Decimal]
    review: Review | None = None
    qualification: QualificationSummary | None = None
    settlement: SettlementModel | None = None
    review_revision_id: str | None = None
    comparison: Comparison | None = None
    assumptions: tuple[str, ...]


class OpportunityState(Model):
    opportunity: Opportunity
    eligible: bool
    status: Literal["eligible", "invalidated"] = "invalidated"
    invalidation_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def reflect_eligibility(self):
        object.__setattr__(self, "status", "eligible" if self.eligible else "invalidated")
        return self


class Evaluation(Model):
    status: Literal["profitable", "unprofitable", "blocked", "invalid"] = "blocked"
    best_calculation: SignedCalculation | None = None
    access_revision_id: str | None = None
    fee_revision_ids: tuple[str, ...] = ()
    match_id: str
    mode: Mode
    evaluated_at: AwareDatetime
    blocked_reasons: tuple[str, ...]
    opportunities: tuple[Opportunity, ...]

    @model_validator(mode="after")
    def legacy_status(self):
        if "status" not in self.model_fields_set:
            object.__setattr__(
                self,
                "status",
                "profitable"
                if self.opportunities
                else (
                    "unprofitable"
                    if self.blocked_reasons == ("no_profitable_size_within_constraints",)
                    else "blocked"
                ),
            )
        return self


def restore(model, payload):
    """Computed output fields are intentionally not accepted as model inputs."""
    return model.model_validate(
        {k: v for k, v in payload.items() if k not in model.model_computed_fields}
    )


POTENTIAL_ASSUMPTIONS = (
    "Assumes complementary ordinary outcomes; exceptional settlement is not qualified.",
    "Account access, balances, borrowing, and account-specific costs are unverified.",
    "Both legs must fill; this gap is not a guaranteed payout or qualified profit.",
)


class PotentialOpportunity(Model):
    """A conditional price gap, never a settlement-qualified opportunity."""

    id: str
    match_id: str
    mode: Mode
    feed_origin: Literal["exchange", "synthetic_recording", "recorded_exchange"]
    evaluated_at: AwareDatetime
    valid_until: AwareDatetime
    market_ids: tuple[str, str]
    book_ids: tuple[str, str]
    terms_hashes: tuple[str, str]
    fee_revision_ids: tuple[str, ...] = ()
    outcomes: tuple[Outcome, Outcome]
    quantity: Positive
    acquisition_cost: NonNegative
    ordinary_payout_assumption: Positive
    gross_spread: Positive
    fee_bound: NonNegative | None = None
    estimated_net_spread: Decimal | None = None
    capital_required: Positive | None = None
    qualification: QualificationSummary
    unresolved_reasons: tuple[str, ...]
    assumptions: tuple[str, ...] = POTENTIAL_ASSUMPTIONS
