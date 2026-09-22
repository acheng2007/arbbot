"""Versioned semantics tests; synthetic rules do not establish live equivalence."""

import json

import httpx
import pytest
from pydantic import ValidationError

from arbbot.api.app import create_app
from arbbot.domain import digest
from arbbot.ingestion.pipeline import Pipeline
from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    V2_FIELDS,
    ContractDefinition,
    compare_contracts,
    definition_hash,
)
from arbbot.matching.service import match_markets
from tests.test_contracts import definition, live_pair


@pytest.mark.parametrize(
    "field,value",
    [
        ("measurement", "month-over-month"),
        ("seasonal_adjustment", "seasonally_adjusted"),
        ("rounding_increment", "0.01"),
        ("rounding_mode", "half_up"),
        ("revision_policy", "final_release"),
        ("revision_policy", "latest_at_deadline"),
        ("observation_start", "2026-01-02T00:00:00-05:00"),
        ("observation_end", "2026-02-02T00:00:00-05:00"),
        ("observation_start_inclusive", "false"),
        ("observation_end_inclusive", "true"),
        ("operator", ">="),
    ],
)
async def test_canonical_conflicts_block_even_new_reviews(fixture_market, field, value):
    markets, _, review, definitions = live_pair(fixture_market)
    definitions[1] = definition(markets[1], **{field: value})
    review = review.model_copy(update={"right_definition_hash": definition_hash(definitions[1])})
    match = match_markets(markets, [review], definitions)[0]
    assert match.status == "candidate"
    assert match.comparison.status == "conflict"
    assert next(d for d in match.comparison.differences if d.field == field).status == "different"


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
@pytest.mark.parametrize("unknown", [False, True])
async def test_missing_or_mutually_unknown_never_compatible(fixture_market, field, unknown):
    markets, _, _, definitions = live_pair(fixture_market)
    reduced = []
    for definition_ in definitions:
        payload = definition_.model_dump(mode="json")
        if unknown:
            payload["facts"][field]["value"] = "unknown"
        else:
            del payload["facts"][field]
        reduced.append(ContractDefinition.model_validate(payload))
    comparison = compare_contracts(*markets, *reduced)
    assert comparison.status == "incomplete"
    assert next(d for d in comparison.differences if d.field == field).status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"seasonal_adjustment": "adjusted"},
        {"rounding_increment": "NaN"},
        {"rounding_increment": "0"},
        {"rounding_increment": "-0.1"},
        {"rounding_increment": "nonsense"},
        {"rounding_increment": "Infinity"},
        {"rounding_mode": "guess"},
        {"rounding_mode": "none"},
        {"revision_policy": "whatever"},
        {"timezone": "EST5EDT-guessed"},
        {"observation_start": "2026-01-01T00:00:00"},
        {"observation_start": "2026-03-01T00:00:00Z"},
        {"observation_start_inclusive": "not_applicable"},
        {"observation_start": "not_applicable"},
        {"observation_end": "2026-01-01T05:00:00Z"},
    ],
)
async def test_invalid_vocabulary_rejected(fixture_market, changes):
    with pytest.raises(ValidationError):
        definition(fixture_market[0][0], **changes)


async def test_numeric_and_instant_equivalence_preserves_exact_evidence(fixture_market):
    markets, _, _, definitions = live_pair(fixture_market)
    equivalent = definition(
        markets[1], rounding_increment="0.10", observation_start="2026-01-01T05:00:00Z"
    )
    assert compare_contracts(*markets, definitions[0], equivalent).status == "compatible"
    assert equivalent.facts["rounding_increment"].value == "0.10"
    # Hashes bind the actual interpretation and evidence, not a lossy normalized copy.
    assert definition_hash(definitions[1]) != definition_hash(equivalent)


async def test_legacy_documents_load_without_approval_or_hash_rewrite(fixture_market):
    markets, _, review, definitions = live_pair(fixture_market)
    legacy = []
    for d in definitions:
        payload = d.model_dump(mode="json")
        payload["schema_version"] = 1
        payload["facts"] = {k: v for k, v in payload["facts"].items() if k not in V2_FIELDS}
        loaded = ContractDefinition.model_validate(payload)
        assert definition_hash(loaded) == digest(payload)
        payload.pop("schema_version")
        assert ContractDefinition.model_validate(payload) == loaded
        legacy.append(loaded)
    review = review.model_copy(
        update={
            "left_definition_hash": definition_hash(legacy[0]),
            "right_definition_hash": definition_hash(legacy[1]),
        }
    )
    comparison = compare_contracts(*markets, *legacy)
    assert comparison.same_event
    assert comparison.status == "incomplete"
    assert "left:definition_schema_upgrade_required" in comparison.issues
    assert match_markets(markets, [review], legacy)[0].status == "candidate"
    # Upgrading definitions cannot reuse the previous approval.
    assert match_markets(markets, [review], definitions)[0].status == "candidate"


async def test_canonical_fields_require_explicit_version(fixture_market):
    payload = definition(fixture_market[0][0]).model_dump(mode="json")
    payload.pop("schema_version")
    with pytest.raises(ValidationError, match="schema_version 2"):
        ContractDefinition.model_validate(payload)


async def test_new_semantics_invalidate_pipeline_opportunities(database, fixture_market, tmp_path):
    settings, db, repository = database
    markets, books, review, definitions = live_pair(fixture_market)
    definitions_file = tmp_path / "definitions.json"
    reviews_file = tmp_path / "reviews.json"
    definitions_file.write_text(json.dumps([d.model_dump(mode="json") for d in definitions]))
    reviews_file.write_text(json.dumps([review.model_dump(mode="json")]))
    settings = settings.model_copy(
        update={
            "mode": "live",
            "definitions_file": definitions_file,
            "reviews_file": reviews_file,
        }
    )

    class Adapter:
        def __init__(self, market):
            self.market, self.venue = market, market.venue

        async def discover(self, limit):
            return [self.market]

        async def fetch_book(self, market):
            return books[market.id]

    pipeline = Pipeline(settings, repository, [Adapter(m) for m in markets])
    assert (await pipeline.cycle())["opportunities"] == 1
    definitions[1] = definition(markets[1], seasonal_adjustment="seasonally_adjusted")
    definitions_file.write_text(json.dumps([d.model_dump(mode="json") for d in definitions]))
    assert (await pipeline.cycle())["opportunities"] == 0
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/opportunities")).json() == []
        match = (await client.get("/api/v1/matches")).json()[0]
        assert match["status"] == "candidate"
        assert match["comparison"]["status"] == "conflict"
        difference = next(
            d for d in match["comparison"]["differences"] if d["field"] == "seasonal_adjustment"
        )
        assert difference["status"] == "different"
