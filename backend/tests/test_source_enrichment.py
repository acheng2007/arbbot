import json
from collections import Counter
from pathlib import Path

import httpx
import pytest

from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.kalshi_sources import enrich_kalshi
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.exchanges.polymarket_sources import enrich_polymarket
from arbbot.sources.fetch import EvidenceError, SourceFetcher
from arbbot.sources.models import MAX_CONTENT_BYTES
from arbbot.sources.repository import SourceRepository

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
async def enrichment(database):
    _, db, repository = database
    records = json.loads((FIXTURES / "contracts/recorded.json").read_text())
    kalshi = KalshiAdapter.normalize_market(records[0]["payload"])
    poly = PolymarketAdapter.normalize_market(
        json.loads((FIXTURES / "polymarket_sources/market.json").read_text())
    )
    for market in (kalshi, poly):
        await repository.save_market(market)
    return SourceRepository(db), kalshi, poly


def responses():
    return {
        "/trade-api/v2/events/KXCPI-26OCT": (FIXTURES / "kalshi_sources/event.json").read_bytes(),
        "/trade-api/v2/series/KXCPI": (FIXTURES / "kalshi_sources/series.json").read_bytes(),
        "/markets/4469383": (FIXTURES / "polymarket_sources/market.json").read_bytes(),
    }


def mock_fetcher(payloads, *, ttl=300):
    calls = Counter()

    def handler(request):
        calls[str(request.url)] += 1
        if request.url.path in payloads:
            return httpx.Response(
                200,
                content=payloads[request.url.path],
                headers={"content-type": "application/json"},
            )
        # Linked document responses are explicit synthetic test data.
        return httpx.Response(
            200, content=b"Recorded-source test document", headers={"content-type": "text/plain"}
        )

    return SourceFetcher(transport=httpx.MockTransport(handler), ttl=ttl), calls


async def test_kalshi_recorded_series_cache_and_changed_terms(enrichment):
    repository, market, _ = enrichment
    payloads = responses()
    fetcher, calls = mock_fetcher(payloads)
    first = await enrich_kalshi(market, repository, fetcher)
    series = first.settlement_details["source_evidence"]["series"]
    assert series["ticker"] == "KXCPI"
    assert series["settlement_sources"]
    assert "jurisdiction" not in first.settlement_details
    assert await enrich_kalshi(market, repository, fetcher) == first
    assert max(calls.values()) == 1
    assert await repository.history("live", market.id)
    data = json.loads(payloads["/trade-api/v2/series/KXCPI"])
    data["series"]["additional_prohibitions"] = ["Synthetic changed terms"]
    payloads["/trade-api/v2/series/KXCPI"] = json.dumps(data).encode()
    fetcher, _ = mock_fetcher(payloads, ttl=0)
    changed = await enrich_kalshi(market, repository, fetcher)
    assert changed.terms_hash != first.terms_hash
    # Audit bytes remain retrievable after source changes.
    history = await repository.history("live", market.id)
    assert len({c.content_digest for c in history if "/series/" in str(c.url)}) == 2


async def test_polymarket_original_rules_and_missing_clarifications(enrichment):
    repository, _, market = enrichment
    fetcher, _ = mock_fetcher(responses())
    result = await enrich_polymarket(market, repository, fetcher)
    assert result.rules == market.rules
    evidence = result.settlement_details["source_evidence"]
    assert evidence["description"] == market.rules
    assert result.settlement_details["source_status"] == "incomplete"
    assert "supplemental_clarifications_unverified" in result.settlement_details["source_issues"]
    assert (await repository.history("live", market.id))[0].content
    assert result.settlement_details["negRisk"] == market.settlement_details["negRisk"]


async def test_volatile_metadata_does_not_change_terms(enrichment):
    repository, _, market = enrichment
    payloads = responses()
    fetcher, _ = mock_fetcher(payloads, ttl=0)
    first = await enrich_polymarket(market, repository, fetcher)
    data = json.loads(payloads["/markets/4469383"])
    data["volume"] = "9999999"
    payloads["/markets/4469383"] = json.dumps(data).encode()
    second = await enrich_polymarket(market, repository, fetcher)
    assert first.terms_hash == second.terms_hash
    assert first.raw["source_artifacts"] != second.raw["source_artifacts"]


@pytest.mark.parametrize("body", [b"{broken", b"[]"])
async def test_malformed_metadata_is_audited_and_incomplete(enrichment, body):
    repository, _, market = enrichment
    fetcher, _ = mock_fetcher({"/markets/4469383": body})
    result = await enrich_polymarket(market, repository, fetcher)
    assert result.settlement_details["source_status"] == "incomplete"
    history = await repository.history("live", market.id)
    assert {c.status for c in history} == {"success", "failure"}


@pytest.mark.parametrize(
    "url",
    [
        "http://www.bls.gov/",
        "https://127.0.0.1/",
        "https://www.bls.gov.evil.test/",
        "https://www.bls.gov/?token=secret",
        "https://user:secret@www.bls.gov/",
        "https://www.bls.gov:8443/",
        "file:///etc/passwd",
    ],
)
async def test_disallowed_urls_make_no_request(url):
    def handler(request):
        pytest.fail("Disallowed URL was requested")

    fetcher = SourceFetcher(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError):
        await fetcher.read(url)


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(302, headers={"location": "https://127.0.0.1/"}), "source_http_302"),
        (
            httpx.Response(
                200, content=b"x" * (MAX_CONTENT_BYTES + 1), headers={"content-type": "text/plain"}
            ),
            "response_too_large",
        ),
        (
            httpx.Response(200, content=b"x", headers={"content-type": "application/octet-stream"}),
            "unsupported_content_type",
        ),
    ],
)
async def test_document_limits_and_redirects(response, code):
    fetcher = SourceFetcher(transport=httpx.MockTransport(lambda r: response))
    with pytest.raises(EvidenceError, match=code):
        await fetcher.read("https://www.bls.gov/")


async def test_retry_recovers_and_caches_success():
    attempts = []

    def handler(request):
        attempts.append(1)
        return (
            httpx.Response(503)
            if len(attempts) < 3
            else httpx.Response(200, content=b"rules", headers={"content-type": "text/plain"})
        )

    fetcher = SourceFetcher(transport=httpx.MockTransport(handler))
    assert (await fetcher.read("https://www.bls.gov/"))[0] == b"rules"
    await fetcher.read("https://www.bls.gov/")
    assert len(attempts) == 3


async def test_enrichment_persists_through_pipeline_and_api(database, enrichment, fixture_market):
    from test_contracts import definition

    from arbbot.api.app import create_app
    from arbbot.ingestion.pipeline import Pipeline
    from arbbot.matching.contracts import evidence_issues

    settings, db, repository = database
    _, market, _ = enrichment
    settings = settings.model_copy(update={"mode": "live"})
    fetcher, _ = mock_fetcher(responses())
    old_definition = definition(market)
    template = next(iter(fixture_market[1].values()))

    class Adapter:
        venue = "kalshi"

        async def discover(self, limit):
            return [market]

        async def enrich_sources(self, item, sources):
            return await enrich_kalshi(item, sources, fetcher)

        async def fetch_book(self, item):
            return template.model_copy(update={"market_id": item.id, "mode": "live"})

    await Pipeline(settings, repository, [Adapter()]).cycle()
    saved = await repository.market("live", market.id)
    assert saved.settlement_details["source_evidence"]["series"]["ticker"] == "KXCPI"
    assert "definition_stale_or_wrong_market" in evidence_issues(saved, old_definition)
    assert await repository.market_version("live", market.id, market.terms_hash)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{market.id}")
        assert response.status_code == 200
        assert response.json()["raw"]["source_artifacts"]
        assert response.json()["settlement_details"]["source_status"] == "captured"


async def test_incomplete_source_prevents_compatible_review(enrichment):
    from test_contracts import definition

    from arbbot.matching.contracts import evidence_issues

    repository, _, market = enrichment
    fetcher, _ = mock_fetcher(responses())
    result = await enrich_polymarket(market, repository, fetcher)
    assert "source_evidence_incomplete" in evidence_issues(result, definition(result))
