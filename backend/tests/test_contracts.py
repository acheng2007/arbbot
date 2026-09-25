import json
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from arbbot.api.app import create_app
from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.domain import utcnow
from arbbot.ingestion.pipeline import Pipeline
from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    ContractDefinition,
    Fact,
    SettlementCondition,
    SettlementPolicy,
    compare_contracts,
    definition_hash,
)
from arbbot.matching.service import match_markets


def definition(market, **changes):
    values = dict.fromkeys(REQUIRED_FIELDS, "explicit_fixture_condition")
    values.update(operator=">", threshold="3.0", outcome_orientation="yes_if_true")
    values.update(
        measurement="year-over-year",
        seasonal_adjustment="not_seasonally_adjusted",
        rounding_increment="0.1",
        rounding_mode="half_even",
        revision_policy="initial_release",
        timezone="America/New_York",
        observation_start="2026-01-01T00:00:00-05:00",
        observation_end="2026-02-01T00:00:00-05:00",
        observation_start_inclusive="true",
        observation_end_inclusive="false",
    )
    values.update(changes)
    return ContractDefinition(
        market_id=market.id,
        terms_hash=market.terms_hash,
        extractor="test-reviewer",
        schema_version=2,
        settlement_policies=(
            SettlementPolicy(
                kind="cancellation",
                status="modeled",
                evidence=Fact(value="fixed_half", source="rules", quote=market.rules),
                conditions=(
                    SettlementCondition(
                        id="cancelled",
                        trigger="Synthetic event cancellation",
                        yes_payout="0.5",
                        no_payout="0.5",
                    ),
                ),
            ),
            *(
                SettlementPolicy(
                    kind=kind,
                    status="not_applicable",
                    evidence=Fact(value="not_applicable", source="rules", quote=market.rules),
                )
                for kind in ("fallback", "ambiguous_resolution")
            ),
        ),
        facts={
            name: Fact(value=value, source="rules", quote=market.rules)
            for name, value in values.items()
        },
    )


def live_pair(fixture):
    markets, books, review, _ = fixture
    markets = [m.model_copy(update={"mode": "live"}) for m in markets]
    definitions = [definition(m) for m in markets]
    review = review.model_copy(
        update={
            "left_definition_hash": definition_hash(definitions[0]),
            "right_definition_hash": definition_hash(definitions[1]),
        }
    )
    books = {k: b.model_copy(update={"mode": "live"}) for k, b in books.items()}
    return markets, books, review, definitions


async def test_structured_event_retrieves_unrelated_titles(fixture_market):
    markets, _, _, _ = live_pair(fixture_market)
    markets[0] = markets[0].model_copy(
        update={"title": "AAA", "closes_at": utcnow() + timedelta(days=90)}
    )
    markets[1] = markets[1].model_copy(update={"title": "ZZZ"})
    definitions = [definition(m) for m in markets]
    matches = match_markets(markets, [], definitions)
    assert len(matches) == 1
    assert matches[0].comparison.same_event
    assert matches[0].status == "candidate"


@pytest.mark.parametrize(
    "field,value",
    [
        ("operator", ">="),
        ("reference_period", "different_month"),
        ("source", "different_publisher"),
        ("value_version", "revised"),
        ("timezone", "Europe/London"),
        ("cancellation", "different_refund"),
        ("outcome_orientation", "yes_if_false"),
    ],
)
async def test_semantic_conflicts_block_review(fixture_market, field, value):
    markets, _, review, definitions = live_pair(fixture_market)
    definitions[1] = definition(markets[1], **{field: value})
    review = review.model_copy(update={"right_definition_hash": definition_hash(definitions[1])})
    match = match_markets(markets, [review], definitions)[0]
    assert match.status == "candidate"
    assert match.comparison.status == "conflict"
    assert next(d for d in match.comparison.differences if d.field == field).status == "different"


async def test_evidence_missing_stale_and_changed_interpretations(fixture_market):
    markets, _, review, definitions = live_pair(fixture_market)
    assert match_markets(markets, [review], definitions)[0].status == "verified"
    assert match_markets(markets, [review])[0].status == "candidate"
    changed = definitions[0].model_copy(update={"extractor": "another-reviewer"})
    assert match_markets(markets, [review], [changed, definitions[1]])[0].status == "candidate"
    stale = definitions[0].model_copy(update={"terms_hash": "0" * 64})
    assert (
        "left:definition_stale_or_wrong_market"
        in compare_contracts(*markets, stale, definitions[1]).issues
    )
    facts = dict(definitions[0].facts)
    facts["source"] = Fact(value="BLS", source="rules", quote="not in these rules")
    bad = definitions[0].model_copy(update={"facts": facts})
    assert (
        "left:evidence_not_found:source" in compare_contracts(*markets, bad, definitions[1]).issues
    )
    facts.pop("source")
    assert (
        compare_contracts(*markets, bad.model_copy(update={"facts": facts}), definitions[1]).status
        == "incomplete"
    )


async def test_decimal_thresholds_and_duplicate_definitions(fixture_market):
    markets, _, _, definitions = live_pair(fixture_market)
    assert (
        compare_contracts(*markets, definitions[0], definition(markets[1], threshold="3.00")).status
        == "compatible"
    )
    with pytest.raises(ValueError, match="Duplicate contract"):
        match_markets(markets, [], [definitions[0], definitions[0]])
    with pytest.raises(ValidationError):
        definition(markets[0], threshold="NaN")


async def test_engine_rechecks_structured_approval(fixture_market):
    markets, books, review, definitions = live_pair(fixture_market)
    match = match_markets(markets, [review], definitions)[0]
    assert evaluate(match, *markets, books, Settings(), utcnow()).opportunities
    forged = match.model_copy(update={"comparison": None})
    assert (
        "structured_equivalence_unverified"
        in evaluate(forged, *markets, books, Settings(), utcnow()).blocked_reasons
    )


async def test_live_definitions_file_through_worker_database_api(
    database, fixture_market, tmp_path
):
    settings, db, repository = database
    markets, books, review, definitions = live_pair(fixture_market)
    definitions_file, reviews_file = tmp_path / "definitions.json", tmp_path / "reviews.json"
    definitions_file.write_text(json.dumps([d.model_dump(mode="json") for d in definitions]))
    reviews_file.write_text(json.dumps([review.model_dump(mode="json")]))
    settings = settings.model_copy(
        update={"mode": "live", "definitions_file": definitions_file, "reviews_file": reviews_file}
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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        match = (await client.get("/api/v1/matches")).json()[0]
        assert match["status"] == "verified"
        assert match["comparison"]["left"]["facts"]["source"]["quote"] == markets[0].rules
        opportunity = (await client.get("/api/v1/opportunities")).json()[0]
        assert opportunity["comparison"]["left_hash"] == definition_hash(definitions[0])
        legacy = review.model_dump(mode="json")
        for scenario in legacy["scenarios"]:
            scenario.pop("left_no")
            scenario.pop("right_no")
        reviews_file.write_text(json.dumps([legacy]))
        assert (await pipeline.cycle())["opportunities"] == 0
        assert (await client.get("/api/v1/opportunities")).json() == []
        candidate = (await client.get("/api/v1/matches")).json()[0]
        assert candidate["status"] == "candidate"
        assert "Explicit settlement payouts" in candidate["reason"]
        reviews_file.write_text(json.dumps([review.model_dump(mode="json")]))
        assert (await pipeline.cycle())["opportunities"] == 1
        uncovered = review.model_dump(mode="json")
        uncovered["settlement_mappings"] = []
        reviews_file.write_text(json.dumps([uncovered]))
        assert (await pipeline.cycle())["opportunities"] == 0
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert (await client.get("/api/v1/matches")).json()[0]["status"] == "candidate"
        reviews_file.write_text(json.dumps([review.model_dump(mode="json")]))
        definitions_file.write_text("[]")
        assert (await pipeline.cycle())["opportunities"] == 0
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert (await client.get("/api/v1/matches")).json()[0]["comparison"][
            "status"
        ] == "incomplete"
