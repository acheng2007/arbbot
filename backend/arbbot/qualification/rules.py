"""Versioned, closed grammars. Unrecognized language cannot acquire compatibility.

The family identity parsers retain the original source wording. The explicit
field grammar supports complete normalized product descriptions; it is not an
LLM output format, and no field is inferred from the absence of a clause.
"""

import re
from dataclasses import dataclass

from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    ContractDefinition,
    Fact,
    SettlementCondition,
    SettlementPolicy,
)
from arbbot.matching.extraction import extract_contract

VERSION = "evidence-rules-v1"
# Complete descriptions must account for every line. In particular, an appended
# amendment, exception, or instruction cannot be ignored by a permissive regex.
FIELD = re.compile(r"(?P<name>[A-Za-z_ ]+)(?:=|: )(?P<value>[^\n]+)")
POLICY = re.compile(
    r"(?P<kind>cancellation|fallback|ambiguous_resolution): "
    r"(?:(?P<na>not applicable)|YES pays (?P<yes>0(?:\.\d+)?|1(?:\.0+)?), "
    r"NO pays (?P<no>0(?:\.\d+)?|1(?:\.0+)?))\."
)


@dataclass(frozen=True)
class FamilyRule:
    name: str
    event_type: str
    metric: str
    version: str = VERSION

    def parse(self, market):
        partial = extract_contract(market).definition
        # Explicit normalized descriptions are accepted only as complete source
        # rules, never from raw metadata, reviewed drafts, or model responses.
        facts, policies, unknown = dict(partial.facts), [], []
        identity_clauses = {f.quote for f in partial.facts.values() if f.source == "rules"}
        for line in market.rules.splitlines():
            if not line.strip():
                continue
            field = FIELD.fullmatch(line)
            policy = POLICY.fullmatch(line)
            name = field["name"].lower().replace(" ", "_") if field else None
            if field and name in REQUIRED_FIELDS and not policy:
                value = field["value"]
                if name in facts and facts[name].value != value:
                    unknown.append("conflicting_field:" + name)
                facts[name] = Fact(value=value, source="rules", quote=line)
            elif line in identity_clauses:
                pass
            elif policy:
                kind = policy["kind"]
                policies.append(
                    SettlementPolicy(
                        kind=kind,
                        status="not_applicable" if policy["na"] else "modeled",
                        evidence=Fact(value=kind, source="rules", quote=line),
                        conditions=()
                        if policy["na"]
                        else (
                            SettlementCondition(
                                id=kind,
                                trigger=f"Explicit {kind} condition in contract rules",
                                yes_payout=policy["yes"],
                                no_payout=policy["no"],
                            ),
                        ),
                    )
                )
            else:
                unknown.append("unrecognized_rule_language")
        if not facts:
            return partial, ("complete_rule_grammar_unavailable",)
        if any(
            facts.get(name) is None or facts[name].value != value
            for name, value in (("event_type", self.event_type), ("metric", self.metric))
        ):
            return partial, ("family_identity_mismatch",)
        definition = ContractDefinition(
            market_id=market.id,
            terms_hash=market.terms_hash,
            extractor=f"{self.name}/{self.version}",
            schema_version=2,
            facts=facts,
            settlement_policies=tuple(policies),
        )
        required_values = {"payout": {"one_usd"}, "outcome_orientation": {"yes_if_true"}}
        if self.name in ("us_cpi", "us_core_cpi"):
            required_values.update(
                entity={"US"},
                source={"US_BLS"},
                units={"percent"},
                measurement={"month-over-month", "year-over-year"},
            )
        elif self.name == "us_fed_rate_hike":
            required_values.update(
                entity={"US"},
                source={"US_FEDERAL_RESERVE"},
                measurement={"target_range_or_level", "upper_bound"},
            )
        else:
            required_values.update(source={"MLB"}, operator={"binary"})
        for name, allowed in required_values.items():
            if name in facts and facts[name].value not in allowed:
                unknown.append("unsupported_field:" + name)
        missing = ["missing_field:" + name for name in REQUIRED_FIELDS if name not in facts]
        return definition, tuple(sorted(set([*unknown, *missing])))


FAMILIES = {
    "us_cpi": FamilyRule("us_cpi", "economic_release", "cpi"),
    "us_core_cpi": FamilyRule("us_core_cpi", "economic_release", "core_cpi"),
    "us_fed_rate_hike": FamilyRule(
        "us_fed_rate_hike", "monetary_policy", "federal_funds_rate_increase"
    ),
    "mlb_championship": FamilyRule(
        "mlb_championship", "sports_championship", "mlb_world_series_winner"
    ),
}


def parse_contract(market):
    partial = extract_contract(market).definition
    metric = partial.facts.get("metric")
    for rule in FAMILIES.values():
        explicit_metric = any(
            (field := FIELD.fullmatch(line))
            and field["name"].lower().replace(" ", "_") == "metric"
            and field["value"] == rule.metric
            for line in market.rules.splitlines()
        )
        if (metric and metric.value == rule.metric) or explicit_metric:
            try:
                return rule.parse(market)
            except ValueError:
                return partial, ("invalid_or_unsupported_contract_language",)
    return partial, ("unsupported_contract_family",)
