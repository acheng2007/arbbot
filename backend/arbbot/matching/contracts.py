"""Evidence-backed interpretations. Extraction proposes facts; reviews approve them."""

from decimal import Decimal, InvalidOperation
from typing import Literal, get_args

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
]
EVENT_FIELDS = ("event_type", "entity", "metric", "reference_period")
REQUIRED_FIELDS = get_args(FieldName)


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
    schema_version: Literal[1] = 1
    facts: dict[FieldName, Fact]

    @model_validator(mode="after")
    def validate_facts(self):
        operator = self.facts.get("operator")
        if operator and operator.value not in {">", ">=", "<", "<=", "=", "binary"}:
            raise ValueError("Unsupported comparison operator")
        threshold = self.facts.get("threshold")
        if threshold and threshold.value != "not_applicable":
            try:
                value = Decimal(threshold.value)
            except InvalidOperation as exc:
                raise ValueError("Threshold must be a decimal or not_applicable") from exc
            if not value.is_finite():
                raise ValueError("Threshold must be finite")
        orientation = self.facts.get("outcome_orientation")
        if orientation and orientation.value not in {"yes_if_true", "yes_if_false"}:
            raise ValueError("Unsupported outcome orientation")
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
        if name == "threshold" and av and bv and "not_applicable" not in (av, bv):
            equal = Decimal(av) == Decimal(bv)
        state = "unknown" if av is None or bv is None else "equal" if equal else "different"
        differences.append(Difference(field=name, status=state, left=av, right=bv))
    same_event = not issues and all(
        d.status == "equal" for d in differences if d.field in EVENT_FIELDS
    )
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
