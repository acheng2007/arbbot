import pytest
from pydantic import ValidationError
from test_contracts import definition, live_pair

from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.domain import utcnow
from arbbot.matching.contracts import (
    V2_FIELDS,
    ContractDefinition,
    Fact,
    compare_contracts,
    definition_hash,
)
from arbbot.matching.service import match_markets


@pytest.mark.parametrize(
    "field,value",
    [
        ("measurement", "month-over-month"),
        ("adjustment", "seasonally_adjusted"),
        ("precision", "2"),
        ("rounding", "half_even"),
        ("revision_policy", "final"),
        ("operator", ">="),
        ("value_version", "revised"),
        ("observation_start", "2026-01-02T00:00:00+00:00"),
        ("observation_end", "2026-02-02T00:00:00+00:00"),
        ("observation_start_inclusive", "false"),
        ("observation_end_inclusive", "true"),
        ("timezone", "America/New_York"),
    ],
)
async def test_vocabulary_conflicts_prevent_live_approval(fixture_market, field, value):
    markets, books, review, definitions = live_pair(fixture_market)
    definitions[1] = definition(markets[1], **{field: value})
    review = review.model_copy(update={"right_definition_hash": definition_hash(definitions[1])})
    match = match_markets(markets, [review], definitions)[0]
    assert match.status == "candidate"
    assert match.comparison.status == "conflict"
    assert not evaluate(match, *markets, books, Settings(), utcnow()).opportunities


@pytest.mark.parametrize("field", (*V2_FIELDS, "threshold", "operator", "timezone"))
@pytest.mark.parametrize("unknown", [False, True])
async def test_missing_or_explicit_unknown_never_approves(fixture_market, field, unknown):
    markets, _, review, definitions = live_pair(fixture_market)
    for i, item in enumerate(definitions):
        data = item.model_dump()
        if unknown:
            data["facts"][field]["value"] = "unknown"
        else:
            data["facts"].pop(field)
        definitions[i] = ContractDefinition.model_validate(data)
    comparison = compare_contracts(*markets, *definitions)
    assert comparison.status == "incomplete"
    assert next(d for d in comparison.differences if d.field == field).status == "unknown"
    review = review.model_copy(
        update={
            "left_definition_hash": definition_hash(definitions[0]),
            "right_definition_hash": definition_hash(definitions[1]),
        }
    )
    assert match_markets(markets, [review], definitions)[0].status == "candidate"


async def test_legacy_round_trip_hash_and_review_invalidation(fixture_market):
    markets, books, review, definitions = live_pair(fixture_market)
    legacy = []
    for item in definitions:
        data = item.model_dump(mode="json")
        data["schema_version"] = 1
        data["facts"] = {k: v for k, v in data["facts"].items() if k not in V2_FIELDS}
        restored = ContractDefinition.model_validate(data)
        assert restored.model_dump(mode="json") == data
        omitted = {k: v for k, v in data.items() if k != "schema_version"}
        assert ContractDefinition.model_validate(omitted) == restored
        assert definition_hash(restored) != definition_hash(item)
        legacy.append(restored)
    review = review.model_copy(
        update={
            "left_definition_hash": definition_hash(legacy[0]),
            "right_definition_hash": definition_hash(legacy[1]),
        }
    )
    match = match_markets(markets, [review], legacy)[0]
    assert match.status == "candidate"
    assert match.comparison.same_event
    assert "left:definition_schema_upgrade_required" in match.comparison.issues
    assert not evaluate(match, *markets, books, Settings(), utcnow()).opportunities
    # Complete v2 facts still need a new review bound to the new hashes.
    assert match_markets(markets, [review], definitions)[0].status == "candidate"


@pytest.mark.parametrize(
    "changes",
    [
        {"precision": "-1"},
        {"precision": "1.5"},
        {"precision": "29"},
        {"adjustment": "guess"},
        {"rounding": "nearest"},
        {"revision_policy": "whatever"},
        {"timezone": "EST-offset-made-up"},
        {"observation_start": "2026-01-01"},
        {"observation_start": "2026-03-01T00:00:00+00:00"},
        {"observation_end_inclusive": "yes"},
    ],
)
async def test_invalid_v2_values_are_rejected(fixture_market, changes):
    with pytest.raises(ValidationError):
        definition(fixture_market[0][0], **changes)


async def test_new_fields_require_v2_and_rules_evidence(fixture_market):
    markets, _, _, definitions = live_pair(fixture_market)
    data = definitions[0].model_dump()
    data["schema_version"] = 1
    with pytest.raises(ValidationError, match="require schema_version 2"):
        ContractDefinition.model_validate(data)
    facts = dict(definitions[0].facts)
    facts["adjustment"] = Fact(value="unadjusted", source="title", quote=markets[0].title)
    bad = definitions[0].model_copy(update={"facts": facts})
    comparison = compare_contracts(*markets, bad, definitions[1])
    assert comparison.status == "incomplete"
    assert "left:rules_evidence_required:adjustment" in comparison.issues
