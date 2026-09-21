"""Evidence-backed interpretations. Extraction proposes facts; reviews approve them."""

from datetime import datetime
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
    "adjustment",
    "precision",
    "rounding",
    "revision_policy",
    "observation_start",
    "observation_end",
    "observation_start_inclusive",
    "observation_end_inclusive",
]
EVENT_FIELDS = ("event_type", "entity", "metric", "reference_period")
REQUIRED_FIELDS = get_args(FieldName)
V2_FIELDS = REQUIRED_FIELDS[16:]
UNKNOWN = "unknown"
# not_applicable is an explicit, evidence-backed assertion, never a default.
VOCABULARY = {
    "measurement": {"year-over-year", "month-over-month", "level", "binary", "not_applicable"},
    "adjustment": {"seasonally_adjusted", "unadjusted", "not_applicable"},
    "rounding": {"half_up", "half_even", "floor", "ceiling", "truncate", "none", "not_applicable"},
    "revision_policy": {"initial", "latest_at_cutoff", "final", "not_applicable"},
    "observation_start_inclusive": {"true", "false", "not_applicable"},
    "observation_end_inclusive": {"true", "false", "not_applicable"},
}


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


class ContractDefinition(StrictModel):
    market_id: str
    terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    extractor: str = Field(min_length=1)
    # Omitted versions remain legacy, avoiding silent upgrades of existing files.
    schema_version: Literal[1, 2] = 1
    facts: dict[FieldName, Fact]

    @model_validator(mode="after")
    def validate_facts(self):
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
        if self.schema_version == 1:
            if any(name in self.facts for name in V2_FIELDS):
                raise ValueError("New settlement fields require schema_version 2")
            return self
        for name, allowed in VOCABULARY.items():
            fact = self.facts.get(name)
            if fact and fact.value not in allowed | {UNKNOWN}:
                raise ValueError(f"Unsupported {name}")
        precision = self.facts.get("precision")
        if precision and precision.value not in {UNKNOWN, "not_applicable"}:
            if not precision.value.isascii() or not precision.value.isdigit():
                raise ValueError("Precision must be a nonnegative decimal-place count")
            if int(precision.value) > 28:
                raise ValueError("Precision must be between 0 and 28 decimal places")
        timezone = self.facts.get("timezone")
        if timezone and timezone.value not in {UNKNOWN, "not_applicable"}:
            try:
                ZoneInfo(timezone.value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Timezone must be an IANA timezone") from exc
        bounds = {}
        for name in ("observation_start", "observation_end"):
            fact = self.facts.get(name)
            if fact and fact.value not in {UNKNOWN, "not_applicable"}:
                try:
                    bound = datetime.fromisoformat(fact.value)
                except ValueError as exc:
                    raise ValueError("Observation bounds must be ISO timestamps") from exc
                if bound.tzinfo is None or bound.utcoffset() is None:
                    raise ValueError("Observation bounds must include an offset")
                bounds[name] = bound
        if len(bounds) == 2 and bounds["observation_start"] > bounds["observation_end"]:
            raise ValueError("Observation start must not follow end")
        return self


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
    if market.settlement_details.get("source_status") == "incomplete":
        issues.append("source_evidence_incomplete")
    if definition.market_id != market.id or definition.terms_hash != market.terms_hash:
        issues.append("definition_stale_or_wrong_market")
    for name, fact in definition.facts.items():
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
        equal = av == bv
        if name == "threshold" and av and bv and not {"not_applicable", UNKNOWN} & {av, bv}:
            equal = Decimal(av) == Decimal(bv)
        state = (
            "unknown"
            if av in (None, UNKNOWN) or bv in (None, UNKNOWN)
            else "equal"
            if equal
            else "different"
        )
        differences.append(Difference(field=name, status=state, left=av, right=bv))
    same_event = not issues and all(
        d.status == "equal" for d in differences if d.field in EVENT_FIELDS
    )
    for side, definition in (("left", a), ("right", b)):
        if definition and definition.schema_version != 2:
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
