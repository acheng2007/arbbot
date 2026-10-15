"""Conservative, local extraction of explicit CPI and Fed rate-hike language.

This parser proposes partial definitions, never settlement approvals or payout assumptions.
CPI reporting periods remain explicit; Fed drafts preserve rule-defined observation windows.
"""

import re
from collections import defaultdict
from typing import Literal

from arbbot.domain import Market
from arbbot.matching.baseball import baseball_facts
from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    ContractDefinition,
    Fact,
    FieldName,
    StrictModel,
)
from arbbot.matching.rate_hike import rate_hike_facts

VERSION = "us-cpi-rules/v2"
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


# Recorded Kalshi primary-rule grammar. Jurisdiction and measurement remain unknown
# until the source agency and series contract are ingested; ticker names are not evidence.
KALSHI_CONDITION = re.compile(
    r"^If the Consumer Price Index \(CPI\) increases by more than "
    r"(?P<threshold>-?\d+(?:\.\d+)?)% \(single-decimal\) in "
    rf"(?P<month>{MONTH_PATTERN}) (?P<year>20\d{{2}}), "
    r"then the market resolves to Yes\.",
    re.IGNORECASE,
)


class Extraction(StrictModel):
    status: Literal["partial", "unsupported", "ambiguous"]
    definition: ContractDefinition
    missing_fields: tuple[FieldName, ...]
    issues: tuple[str, ...]


def extract_contract(market: Market) -> Extraction:
    sports = baseball_facts(market)
    if sports:
        return Extraction(
            status="partial",
            definition=ContractDefinition(
                market_id=market.id,
                terms_hash=market.terms_hash,
                schema_version=2,
                extractor="mlb-championship-rules/v1",
                facts=sports,
            ),
            missing_fields=tuple(n for n in REQUIRED_FIELDS if n not in sports),
            issues=("exceptional_settlement_and_source_review_required",),
        )
    rate_facts = rate_hike_facts(market)
    if rate_facts:
        return Extraction(
            status="partial",
            definition=ContractDefinition(
                market_id=market.id,
                terms_hash=market.terms_hash,
                extractor="fed-rate-hike-rules/v1",
                schema_version=2,
                facts=rate_facts,
            ),
            missing_fields=tuple(name for name in REQUIRED_FIELDS if name not in rate_facts),
            issues=("source_and_exception_review_required",),
        )
    candidates: dict[str, list[Fact]] = defaultdict(list)
    issues = []

    def propose(field, value, source, quote):
        candidates[field].append(Fact(value=value, source=source, quote=quote))

    if market.venue == "kalshi":
        condition = KALSHI_CONDITION.match(market.rules)
        if condition:
            month = next(
                i for i, name in enumerate(MONTHS, 1) if name.lower() == condition["month"].lower()
            )
            for field, value in {
                "event_type": "economic_release",
                "metric": "cpi",
                "reference_period": f"{condition['year']}-{month:02}",
                "operator": ">",
                "threshold": condition["threshold"],
                "units": "percent",
                "outcome_orientation": "yes_if_true",
            }.items():
                propose(field, value, "rules", condition.group())

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
