"""Synthetic language fixtures; these are not claims about live exchange listings."""

import httpx
import pytest

from arbbot.api.app import create_app
from arbbot.ingestion.pipeline import Pipeline
from arbbot.matching.contracts import evidence_issues
from arbbot.matching.extraction import extract_contract


def cpi_market(market, *, rules=None, title="US CPI for August 2026"):
    return market.model_copy(
        update={
            "title": title,
            "rules": rules
            if rules is not None
            else (
                "This market resolves to YES if the US CPI year-over-year change "
                "for August 2026 is above 3.0%. Source: Bureau of Labor Statistics."
            ),
            "mode": "live",
        }
    )


async def test_partial_definition_has_verbatim_evidence(fixture_market):
    market = cpi_market(fixture_market[0][0])
    result = extract_contract(market)
    assert result.status == "partial"
    assert not evidence_issues(market, result.definition)
    values = {k: f.value for k, f in result.definition.facts.items()}
    assert values == {
        "event_type": "economic_release",
        "entity": "US",
        "metric": "cpi",
        "reference_period": "2026-08",
        "measurement": "year-over-year",
        "operator": ">",
        "threshold": "3.0",
        "units": "percent",
        "outcome_orientation": "yes_if_true",
        "source": "US_BLS",
    }
    assert {
        "cancellation",
        "exceptions",
        "value_version",
        "payout",
        "timezone",
        "observation_window",
        "adjustment",
        "precision",
        "rounding",
        "revision_policy",
        "observation_start",
        "observation_end",
        "observation_start_inclusive",
        "observation_end_inclusive",
    } == set(result.missing_fields)


@pytest.mark.parametrize(
    "language,operator",
    [
        ("above", ">"),
        ("at least", ">="),
        ("below", "<"),
        ("at most", "<="),
    ],
)
async def test_operator_and_signed_decimal_extraction(fixture_market, language, operator):
    market = cpi_market(
        fixture_market[0][0],
        title="U.S. core CPI for January 2027",
        rules=(
            f"Settles YES if U.S. core Consumer Price Index month over month rate "
            f"for January 2027 is {language} -0.25 percent."
        ),
    )
    result = extract_contract(market)
    assert result.definition.facts["metric"].value == "core_cpi"
    assert result.definition.facts["measurement"].value == "month-over-month"
    assert result.definition.facts["operator"].value == operator
    assert result.definition.facts["threshold"].value == "-0.25"


async def test_conflicting_title_and_rules_do_not_choose_a_period(fixture_market):
    result = extract_contract(cpi_market(fixture_market[0][0], title="US CPI for July 2026"))
    assert result.status == "ambiguous"
    assert "conflicting_values:reference_period" in result.issues
    assert "reference_period" not in result.definition.facts


async def test_no_threshold_from_title_or_incidental_statistics(fixture_market):
    market = cpi_market(
        fixture_market[0][0],
        title="US CPI above 3% for August 2026",
        rules=(
            "US CPI for August 2026. Last month's rate was 3%. "
            "Resolves NO if US CPI year-over-year change for August 2026 is above 4%."
        ),
    )
    result = extract_contract(market)
    assert "threshold" not in result.definition.facts
    assert "operator" not in result.definition.facts


async def test_release_date_is_not_reporting_period(fixture_market):
    market = cpi_market(fixture_market[0][0], title="US CPI on September 11, 2026", rules="")
    result = extract_contract(market)
    assert "reference_period" in result.missing_fields
    assert "explicit_reporting_period_required" in result.issues


async def test_unsupported_markets_produce_empty_drafts(fixture_market):
    market = cpi_market(
        fixture_market[0][0], title="Will a team win?", rules="Sporting event rules"
    )
    result = extract_contract(market)
    assert result.status == "unsupported"
    assert result.definition.facts == {}


async def test_conflicting_conditions_leave_operator_unknown(fixture_market):
    market = cpi_market(fixture_market[0][0])
    market = market.model_copy(
        update={
            "rules": market.rules
            + (
                " This market resolves YES if US CPI year-over-year change "
                "for August 2026 is at least 3.0%."
            )
        }
    )
    result = extract_contract(market)
    assert result.status == "ambiguous"
    assert "operator" not in result.definition.facts


async def test_automatic_drafts_flow_from_ingestion_to_api(database, fixture_market):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live"})
    markets = [
        cpi_market(m, title=t)
        for m, t in zip(
            fixture_market[0], ("Economic release A", "Inflation threshold B"), strict=True
        )
    ]

    class Adapter:
        def __init__(self, market):
            self.market, self.venue = market, market.venue

        async def discover(self, limit):
            return [self.market]

        async def fetch_book(self, market):
            return fixture_market[1][market.id].model_copy(update={"mode": "live"})

    pipeline = Pipeline(settings, repository, [Adapter(m) for m in markets])
    result = await pipeline.cycle()
    assert result["matches"] == 1
    assert result["opportunities"] == 0
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{markets[0].id}/extraction")
        assert response.status_code == 200
        assert response.json()["status"] == "partial"
        match = (await client.get("/api/v1/matches")).json()[0]
        assert match["status"] == "candidate"
        assert match["comparison"]["same_event"]
        assert match["comparison"]["status"] == "incomplete"
        assert match["comparison"]["left"] == response.json()["definition"]
        assert (await client.get("/api/v1/markets/missing/extraction")).status_code == 404
        live_schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/markets/{market_id}/extraction" in live_schema["paths"]
    # Endpoint reads the latest terms, not a stale draft from the previous cycle.
    changed = markets[0].model_copy(update={"rules": "Unknown rules", "title": "Unknown"})
    await repository.save_market(changed)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        payload = (await client.get(f"/api/v1/markets/{changed.id}/extraction")).json()
        assert payload["definition"]["terms_hash"] == changed.terms_hash
        assert payload["status"] == "unsupported"
    # Simulation API cannot expose live drafts.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=create_app(settings.model_copy(update={"mode": "simulation"}), db)
        ),
        base_url="http://test",
    ) as client:
        assert (await client.get(f"/api/v1/markets/{markets[0].id}/extraction")).status_code == 404
