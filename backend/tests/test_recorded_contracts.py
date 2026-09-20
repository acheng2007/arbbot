"""Replay immutable public metadata through adapters, extraction, storage and REST."""

import json
from pathlib import Path

import httpx
import pytest

from arbbot.api.app import create_app
from arbbot.config import Settings
from arbbot.domain import digest
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.matching.contracts import compare_contracts, evidence_issues
from arbbot.matching.corpus import evaluate_corpus, normalize_record, supported_record
from arbbot.matching.extraction import extract_contract

ROOT = Path(__file__).parent / "fixtures" / "contracts"
RECORDS = json.loads((ROOT / "recorded.json").read_text())
LABELS = json.loads((ROOT / "labels.json").read_text())


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: normalize_record(r).id)
async def test_recorded_metadata_preserves_provenance_and_never_invents_facts(record):
    market = normalize_record(record)
    label = LABELS[market.id]
    assert digest(record["payload"]) == label["payload_sha256"]
    assert supported_record(record) == label["supported_by_adapter"]
    result = extract_contract(market)
    assert not evidence_issues(market, result.definition)
    for name, fact in result.definition.facts.items():
        assert fact.value == label["facts"].get(name), name
    assert {"cancellation", "exceptions", "payout"}.issubset(result.missing_fields)


async def test_recorded_coverage_report_exposes_missing_fields():
    report = evaluate_corpus(RECORDS, LABELS)
    assert report["markets"] == 9
    assert report["supported_by_adapter"] == 3
    assert report["labeled_fields"] == 63
    assert report["incorrect_fields"] == 0
    assert report["correct_fields"] >= 14
    # Missing coverage is visible, never conflated with successful extraction.
    assert (
        report["correct_fields"] + sum(len(r["missing_labeled_fields"]) for r in report["results"])
        == report["labeled_fields"]
    )


@pytest.mark.parametrize(
    "left_id,right_id",
    [
        ("polymarket:4469383", "polymarket:4469455"),  # Annual vs monthly.
        ("polymarket:3539685", "polymarket:3938028"),  # CPI vs PCE.
        ("polymarket:3539685", "polymarket:3586722"),  # US vs Argentina.
        ("polymarket:3539685", "polymarket:3499774"),  # US vs China.
        ("kalshi:KXCPI-26OCT-T1.0", "polymarket:4469455"),  # Different months.
    ],
)
async def test_recorded_near_matches_cannot_be_approved(left_id, right_id):
    markets = {m.id: m for m in map(normalize_record, RECORDS)}
    left, right = markets[left_id], markets[right_id]
    comparison = compare_contracts(
        left, right, extract_contract(left).definition, extract_contract(right).definition
    )
    assert comparison.status != "compatible"


async def test_recorded_discovery_to_extraction_api(database):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live"})
    requests = []

    def response(request):
        requests.append(str(request.url))
        if request.url.host == "external-api.kalshi.com":
            return httpx.Response(
                200,
                json={
                    "markets": [r["payload"] for r in RECORDS if r["venue"] == "kalshi"],
                    "cursor": "",
                },
            )
        return httpx.Response(
            200,
            json={
                "markets": [r["payload"] for r in RECORDS if r["venue"] == "polymarket"],
                "next_cursor": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        http = ExchangeHTTP(client, interval=0)
        kalshi = await KalshiAdapter(http, Settings(_env_file=None)).discover(20)
        poly = await PolymarketAdapter(http).discover(20)
    assert len(requests) == 2
    assert len(kalshi) == 2
    assert all(not market.raw.get("negRisk") for market in poly)
    for market in kalshi + poly:
        await repository.save_market(market)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        for market in kalshi + poly:
            result = await client.get(f"/api/v1/markets/{market.id}/extraction")
            assert result.status_code == 200
            assert result.json()["definition"]["terms_hash"] == market.terms_hash
            assert "payout" in result.json()["missing_fields"]
            if market.venue == "kalshi":
                assert result.json()["status"] == "partial"
                assert (
                    result.json()["definition"]["facts"]["reference_period"]["value"] == "2026-10"
                )
                assert "entity" in result.json()["missing_fields"]
                assert "source" in result.json()["missing_fields"]
        assert (await client.get("/api/v1/opportunities")).json() == []
