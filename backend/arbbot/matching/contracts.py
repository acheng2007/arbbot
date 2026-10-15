"""Evidence-backed interpretations. Extraction proposes facts; reviews approve them."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldName = Literal[
    "event_type",
    "entity",
    "metric",
    "reference_period",
    "measurement",
    "source",
    "value_version",
    "operator",
    "threshold",
    "units",
    "observation_window",
    "timezone",
    "outcome_orientation",
    "payout",
    "cancellation",
    "exceptions",
    "seasonal_adjustment",
    "rounding_increment",
    "rounding_mode",
    "revision_policy",
    "observation_start",
    "observation_end",
    "observation_start_inclusive",
    "observation_end_inclusive",
]
EVENT_FIELDS = ("event_type", "entity", "metric", "reference_period")
REQUIRED_FIELDS = get_args(FieldName)
CURRENT_SCHEMA_VERSION = 2
V2_FIELDS = frozenset(
    {
        "seasonal_adjustment",
        "rounding_increment",
        "rounding_mode",
        "revision_policy",
        "observation_start",
        "observation_end",
        "observation_start_inclusive",
        "observation_end_inclusive",
    }
)
UNKNOWN = "unknown"
VOCABULARY = {
    "measurement": {
        "month-over-month",
        "year-over-year",
        "level",
        "not_applicable",
        "target_range_or_level",
        "upper_bound",
        "point_in_time",
        "window_max",
    },
    "seasonal_adjustment": {"seasonally_adjusted", "not_seasonally_adjusted", "not_applicable"},
    "rounding_mode": {
        "half_even",
        "half_up",
        "half_down",
        "floor",
        "ceiling",
        "toward_zero",
        "away_from_zero",
        "none",
        "not_applicable",
    },
    "revision_policy": {"initial_release", "final_release", "latest_at_deadline", "not_applicable"},
    "observation_start_inclusive": {"true", "false", "not_applicable"},
    "observation_end_inclusive": {"true", "false", "not_applicable"},
}


def observation_instant(value: str) -> datetime:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Observation bounds require a timezone offset")
    return instant.astimezone(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Fact(StrictModel):
    value: str = Field(min_length=1)
    source: Literal["title", "rules", "settlement_details"]
    # settlement_details evidence refers to one top-level string field.
    source_key: str | None = None
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_value(self):
        if not self.value.strip() or not self.quote.strip():
            raise ValueError("Values and evidence cannot be blank")
        if (self.source == "settlement_details") != (self.source_key is not None):
            raise ValueError("Only settlement_details requires a source_key")
        return self


class SettlementCondition(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    trigger: str = Field(min_length=10, max_length=2000)
    yes_payout: Decimal = Field(ge=0, le=1, allow_inf_nan=False)
    no_payout: Decimal = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def complementary(self):
        if self.yes_payout + self.no_payout != 1:
            raise ValueError("Non-complementary settlement conditions are unsupported")
        return self


class SettlementPolicy(StrictModel):
    kind: Literal["cancellation", "fallback", "ambiguous_resolution"]
    status: Literal["modeled", "not_applicable", "unknown"]
    evidence: Fact
    conditions: tuple[SettlementCondition, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def conditions_match_status(self):
        if (self.status == "modeled") != bool(self.conditions):
            raise ValueError("Only modeled policies require settlement conditions")
        if len({c.id for c in self.conditions}) != len(self.conditions):
            raise ValueError("Settlement condition identifiers must be unique within a policy")
        if self.evidence.source == "title":
            raise ValueError("Settlement policies require rules evidence")
        return self


class ContractDefinition(StrictModel):
    market_id: str
    terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    extractor: str = Field(min_length=1)
    # Missing versions retain legacy semantics and cannot silently gain approval.
    schema_version: Literal[1, 2] = 1
    facts: dict[FieldName, Fact]
    settlement_policies: tuple[SettlementPolicy, ...] | None = Field(default=None, max_length=3)

    @model_validator(mode="after")
    def validate_facts(self):
        if self.settlement_policies is not None and len(
            {p.kind for p in self.settlement_policies}
        ) != len(self.settlement_policies):
            raise ValueError("Settlement policy kinds must be unique")
        if self.schema_version == 1 and V2_FIELDS.intersection(self.facts):
            raise ValueError("Canonical measurement fields require schema_version 2")
        operator = self.facts.get("operator")
        if operator and operator.value not in {">", ">=", "<", "<=", "=", "binary", UNKNOWN}:
            raise ValueError("Unsupported comparison operator")
        threshold = self.facts.get("threshold")
        if threshold and threshold.value not in {"not_applicable", UNKNOWN}:
            try:
                value = Decimal(threshold.value)
            except InvalidOperation as exc:
                raise ValueError("Threshold must be a decimal or not_applicable") from exc
            if not value.is_finite():
                raise ValueError("Threshold must be finite")
        orientation = self.facts.get("outcome_orientation")
        if orientation and orientation.value not in {"yes_if_true", "yes_if_false", UNKNOWN}:
            raise ValueError("Unsupported outcome orientation")
        if self.schema_version == CURRENT_SCHEMA_VERSION:
            self.validate_vocabulary()
        return self

    def validate_vocabulary(self):
        values = {name: fact.value for name, fact in self.facts.items()}
        for name, choices in VOCABULARY.items():
            if name in values and values[name] not in choices | {UNKNOWN}:
                raise ValueError(f"Unsupported canonical {name}")
        increment = values.get("rounding_increment")
        if increment not in {None, UNKNOWN, "none", "not_applicable"}:
            try:
                number = Decimal(increment)
            except InvalidOperation as exc:
                raise ValueError("Rounding increment must be a positive decimal") from exc
            if not number.is_finite() or number <= 0:
                raise ValueError("Rounding increment must be a positive finite decimal")
        rounding_mode = values.get("rounding_mode")
        if increment not in {None, UNKNOWN} and rounding_mode not in {None, UNKNOWN}:
            if (
                increment in {"none", "not_applicable"}
                or rounding_mode in {"none", "not_applicable"}
            ) and increment != rounding_mode:
                raise ValueError("Rounding mode and increment disagree")
        timezone = values.get("timezone")
        if timezone not in {None, UNKNOWN, "not_applicable"}:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Timezone must be an IANA timezone identifier") from exc
        bounds = {}
        for side in ("start", "end"):
            value = values.get(f"observation_{side}")
            inclusive = values.get(f"observation_{side}_inclusive")
            if value not in {None, UNKNOWN, "not_applicable"}:
                bounds[side] = observation_instant(value)
                if inclusive == "not_applicable":
                    raise ValueError("An observation bound requires an inclusion policy")
            elif value == "not_applicable" and inclusive not in {None, UNKNOWN, "not_applicable"}:
                raise ValueError("An absent bound cannot have an inclusion policy")
        if "start" in bounds and "end" in bounds:
            if bounds["start"] > bounds["end"]:
                raise ValueError("Observation start must not follow its end")
            if bounds["start"] == bounds["end"] and any(
                values.get(f"observation_{side}_inclusive") == "false" for side in ("start", "end")
            ):
                raise ValueError("Observation interval must not be empty")


class Difference(StrictModel):
    field: str
    status: Literal["equal", "different", "unknown"]
    left: str | None
    right: str | None


class Comparison(StrictModel):
    status: Literal["compatible", "conflict", "incomplete"]
    same_event: bool
    event_key: str | None = None
    left: ContractDefinition | None
    right: ContractDefinition | None
    left_hash: str | None
    right_hash: str | None
    differences: tuple[Difference, ...]
    issues: tuple[str, ...]


def definition_hash(definition):
    from arbbot.domain import digest

    return digest(definition.model_dump(mode="json")) if definition else None


def evidence_issues(market, definition):
    if definition is None:
        return ["definition_missing"]
    issues = []
    if definition.market_id != market.id or definition.terms_hash != market.terms_hash:
        issues.append("definition_stale_or_wrong_market")
    facts = list(definition.facts.items())
    facts.extend(
        (f"settlement_policy:{policy.kind}", policy.evidence)
        for policy in definition.settlement_policies or ()
    )
    for name, fact in facts:
        source = getattr(market, fact.source)
        if fact.source == "settlement_details":
            source = source.get(fact.source_key)
        if not isinstance(source, str) or fact.quote not in source:
            issues.append(f"evidence_not_found:{name}")
        # Titles can identify an event, but cannot substantiate settlement semantics.
        if name not in EVENT_FIELDS and fact.source == "title":
            issues.append(f"rules_evidence_required:{name}")
    return issues


def compare_contracts(left, right, a=None, b=None):
    issues = [f"left:{issue}" for issue in evidence_issues(left, a)]
    issues += [f"right:{issue}" for issue in evidence_issues(right, b)]
    differences = []
    for name in REQUIRED_FIELDS:
        av = a.facts[name].value if a and name in a.facts else None
        bv = b.facts[name].value if b and name in b.facts else None
        av = None if av == UNKNOWN else av
        bv = None if bv == UNKNOWN else bv
        equal = av == bv
        if (
            name in {"threshold", "rounding_increment"}
            and av
            and bv
            and not ({av, bv} & {"not_applicable", "none"})
        ):
            equal = Decimal(av) == Decimal(bv)
        if (
            name in {"observation_start", "observation_end"}
            and av
            and bv
            and ("not_applicable" not in (av, bv))
        ):
            equal = observation_instant(av) == observation_instant(bv)
        state = "unknown" if av is None or bv is None else "equal" if equal else "different"
        differences.append(Difference(field=name, status=state, left=av, right=bv))
    same_event = not issues and all(
        d.status == "equal" for d in differences if d.field in EVENT_FIELDS
    )
    # Retrieval gaps block settlement compatibility, but a documented event
    # identity can still be displayed as a candidate comparison.
    for side, market in (("left", left), ("right", right)):
        if market.mode == "live" and market.settlement_details.get("source_status") == "incomplete":
            issues.append(f"{side}:source_evidence_incomplete")
    for side, definition in (("left", a), ("right", b)):
        if definition and definition.schema_version != CURRENT_SCHEMA_VERSION:
            issues.append(f"{side}:definition_schema_upgrade_required")
    status = (
        "conflict"
        if any(d.status == "different" for d in differences)
        else "incomplete"
        if issues or any(d.status == "unknown" for d in differences)
        else "compatible"
    )
    from arbbot.domain import digest

    return Comparison(
        event_key=digest([a.facts[name].value for name in EVENT_FIELDS]) if same_event else None,
        status=status,
        same_event=same_event,
        left=a,
        right=b,
        left_hash=definition_hash(a),
        right_hash=definition_hash(b),
        differences=tuple(differences),
        issues=tuple(issues),
    )
