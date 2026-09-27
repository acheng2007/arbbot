import json
from datetime import datetime
from pathlib import Path

import pytest

from arbbot.domain import digest
from arbbot.matching.contracts import ContractDefinition, Fact, compare_contracts, evidence_issues
from arbbot.matching.corpus import normalize_record, supported_record
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets

ROOT = Path(__file__).parent / "fixtures/cross_exchange"
RECORDS = json.loads((ROOT / "recorded.json").read_text())
LABELS = json.loads((ROOT / "labels.json").read_text())
MARKETS = {normalize_record(record).id: normalize_record(record) for record in RECORDS}


def labeled_definition(market):
    label = LABELS["markets"][market.id]
    return ContractDefinition(
        market_id=market.id,
        terms_hash=market.terms_hash,
        extractor="source-reading-regression-labels",
        schema_version=2,
        facts={
            name: Fact(value=value, source="rules", quote=label["quote"] or market.rules)
            for name, value in label["facts"].items()
        },
    )


def test_recorded_sources_have_unchanged_payloads_and_supported_instruments():
    assert len(RECORDS) == len(LABELS["markets"]) == 8
    assert {label["family"] for label in LABELS["markets"].values()} == {
        "fed_rate_hike",
        "recession",
        "treasury_yield",
    }
    for record in RECORDS:
        market = normalize_record(record)
        assert record["source_url"].startswith("https://")
        assert datetime.fromisoformat(record["captured_at"]).tzinfo
        assert digest(record["payload"]) == LABELS["markets"][market.id]["digest"]
        assert supported_record(record)
        assert not evidence_issues(market, labeled_definition(market))


@pytest.mark.parametrize("pair", LABELS["pairs"], ids=lambda p: p["label"])
def test_offline_adapter_to_comparison_preserves_material_differences(pair):
    left, right = MARKETS[pair["left"]], MARKETS[pair["right"]]
    comparison = compare_contracts(left, right, labeled_definition(left), labeled_definition(right))
    assert comparison.same_event == pair["same_event"]
    assert comparison.status == "conflict"
    conflicts = {d.field for d in comparison.differences if d.status == "different"}
    assert set(pair["conflicts"]).issubset(conflicts)
    matches = match_markets(
        [left, right], [], [labeled_definition(left), labeled_definition(right)]
    )
    assert all(match.status != "verified" for match in matches)


def test_rate_hike_extraction_replays_supported_same_event_candidate():
    markets = [MARKETS[key] for key in ("kalshi:KXFEDHIKE-2-26DEC31", "polymarket:4620900")]
    drafts = [extract_contract(market) for market in markets]
    for market, draft in zip(markets, drafts, strict=True):
        assert draft.status == "partial"
        assert {k: f.value for k, f in draft.definition.facts.items()} == LABELS["markets"][
            market.id
        ]["facts"]
        assert not evidence_issues(market, draft.definition)
        assert draft.definition.settlement_policies is None
    comparison = compare_contracts(*markets, *(d.definition for d in drafts))
    assert comparison.same_event
    assert comparison.status == "conflict"
    match = match_markets(markets, [], [d.definition for d in drafts])[0]
    assert match.status == "candidate" and match.review is None


def test_title_alone_or_changed_rate_condition_cannot_supply_rate_hike_identity():
    market = MARKETS["polymarket:4620900"]
    for rules in ("Rules pending", market.rules.replace("is increased", "is decreased")):
        assert not extract_contract(market.model_copy(update={"rules": rules})).definition.facts
