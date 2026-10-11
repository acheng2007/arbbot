import httpx

from arbbot.exchanges.polymarket_us_sources import enrich_polymarket_us
from arbbot.sources.fetch import SourceFetcher
from arbbot.sources.repository import SourceRepository
from tests.test_polymarket_us import pair, recorded


async def test_official_us_documents_have_text_and_explicit_applicability_gaps(database):
    _, db, repository = database
    market = pair()[1]
    await repository.save_market(market)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.host == "gateway.polymarket.us":
            return httpx.Response(200, json=recorded("polymarket-us-dodgers.json"))
        if request.url.path in {"/files/products", "/files/notices"}:
            return httpx.Response(200, json={"files": []})
        return httpx.Response(
            200, text="US rulebook. Exceptional settlement is subject to product terms."
        )

    fetcher = SourceFetcher(transport=httpx.MockTransport(handler))
    sources = SourceRepository(db)
    enriched = await enrich_polymarket_us(market, sources, fetcher)
    assert len(calls) == 4
    assert enriched.settlement_details["source_status"] == "incomplete"
    assert (
        "product_specification_applicability_unverified"
        in enriched.settlement_details["source_issues"]
    )
    assert "US rulebook." in enriched.settlement_details["source_text_polymarket_us_rulebook"]
    provenance = enriched.settlement_details["source_text_provenance"][0]
    assert provenance["status"] == "complete" and provenance["text_digest"]
    artifact = await sources.get("live", provenance["artifact_id"])
    assert artifact.content_digest == provenance["content_digest"]
    assert artifact.url.startswith("https://polymarketexchange.com/")


async def test_gateway_identity_change_never_becomes_complete_evidence(database):
    _, db, repository = database
    market = pair()[1]
    await repository.save_market(market)
    raw = recorded("polymarket-us-dodgers.json")
    raw["market"]["slug"] = "different-instrument"
    fetcher = SourceFetcher(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=raw))
    )
    enriched = await enrich_polymarket_us(market, SourceRepository(db), fetcher)
    assert enriched.settlement_details["source_status"] == "incomplete"
    assert "missing_or_wrong_gateway_instrument" in enriched.settlement_details["source_issues"]


async def test_official_legal_alias_resolves_only_within_verified_host():
    import pytest

    from arbbot.sources.fetch import EvidenceError

    def response(request):
        if "/latest/" in request.url.path:
            return httpx.Response(302, headers={"location": "/files/legal/Rulebook.pdf"})
        return httpx.Response(200, text="Captured rulebook")

    fetcher = SourceFetcher(transport=httpx.MockTransport(response))
    url = "https://polymarketexchange.com/files/legal/latest/rulebook"
    content, _, _ = await fetcher.read(url)
    assert content == b"Captured rulebook"
    assert fetcher.resolved_urls[url].endswith("/files/legal/Rulebook.pdf")
    fetcher = SourceFetcher(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                302, headers={"location": "https://example.com/rulebook"}
            )
        )
    )
    with pytest.raises(EvidenceError, match="source_redirect_not_allowed"):
        await fetcher.read(url)
