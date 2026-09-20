"""Conservative, local extraction of explicit US CPI contract language.

This parser proposes partial definitions. It never supplies settlement exceptions,
unit payout assumptions, or approval, and does not infer reporting periods from dates.
"""

import re
from collections import defaultdict
from typing import Literal

from arbbot.domain import Market
from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    ContractDefinition,
    Fact,
    FieldName,
    StrictModel,
)

VERSION = "us-cpi-rules/v1"
MONTHS = (
    "January February March April May June July August September October November December"
).split()
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + ")"
# Require an explicit jurisdiction and distinguish core from headline.
SUBJECT = r"(?:US|U\.S\.)\s+(?P<core>core\s+)?(?:CPI|Consumer Price Index)\b"
PERIOD = rf"\bfor\s+(?P<month>{MONTH_PATTERN})\s+(?P<year>20\d{{2}})\b"
MEASURE = r"(?P<measure>year[- ]over[- ]year|month[- ]over[- ]month)"
OPERATORS = {
    "above": ">",
    "greater than": ">",
    "at least": ">=",
    "below": "<",
    "less than": "<",
    "at most": "<=",
}
# Only parse an affirmative, explicit YES condition, rather than incidental numbers.
CONDITION = re.compile(
    rf"(?:resolves?|settles?)\s+(?:to\s+)?YES\s+if\s+(?:the\s+)?{SUBJECT}"
    rf"\s+{MEASURE}\s+(?:change|rate)\s+{PERIOD}\s+is\s+"
    r"(?P<operator>above|greater than|at least|below|less than|at most)\s+"
    r"(?P<threshold>-?\d+(?:\.\d+)?)\s*(?:%|percent\b)",
    re.IGNORECASE,
)


class Extraction(StrictModel):
    status: Literal["partial", "unsupported", "ambiguous"]
    definition: ContractDefinition
    missing_fields: tuple[FieldName, ...]
    issues: tuple[str, ...]


def extract_contract(market: Market) -> Extraction:
    candidates: dict[str, list[Fact]] = defaultdict(list)
    issues = []

    def propose(field, value, source, quote):
        candidates[field].append(Fact(value=value, source=source, quote=quote))

    for source in ("rules", "title"):
        text = getattr(market, source)
        subjects = list(re.finditer(SUBJECT, text, re.IGNORECASE))
        if not subjects:
            continue
        for subject in subjects:
            quote = subject.group()
            propose("event_type", "economic_release", source, quote)
            propose("entity", "US", source, quote)
            propose("metric", "core_cpi" if subject["core"] else "cpi", source, quote)
        for period in re.finditer(PERIOD, text, re.IGNORECASE):
            month = next(i for i, m in enumerate(MONTHS, 1) if m.lower() == period["month"].lower())
            propose("reference_period", f"{period['year']}-{month:02}", source, period.group())

    if candidates:
        for condition in CONDITION.finditer(market.rules):
            quote = condition.group()
            measure = condition["measure"].lower().replace(" ", "-")
            propose("measurement", measure, "rules", quote)
            propose("operator", OPERATORS[condition["operator"].lower()], "rules", quote)
            propose("threshold", condition["threshold"], "rules", quote)
            propose("units", "percent", "rules", quote)
            propose("outcome_orientation", "yes_if_true", "rules", quote)
        for publisher in re.finditer(
            r"\b(?:U\.S\.\s+)?Bureau of Labor Statistics\b", market.rules, re.IGNORECASE
        ):
            propose("source", "US_BLS", "rules", publisher.group())

    facts = {}
    for field, proposals in candidates.items():
        if len({p.value for p in proposals}) != 1:
            issues.append(f"conflicting_values:{field}")
        else:
            facts[field] = proposals[0]  # Prefer rules evidence to title evidence.
    if not candidates:
        issues.append("unsupported_event_language")
    if "reference_period" not in facts:
        issues.append("explicit_reporting_period_required")
    # These fields always require further interpretation. No automatic approval path.
    definition = ContractDefinition(
        market_id=market.id,
        terms_hash=market.terms_hash,
        extractor=VERSION,
        facts=facts,
    )
    return Extraction(
        status="ambiguous"
        if any(i.startswith("conflicting_values:") for i in issues)
        else "partial"
        if candidates
        else "unsupported",
        definition=definition,
        missing_fields=tuple(name for name in REQUIRED_FIELDS if name not in facts),
        issues=tuple(issues),
    )
