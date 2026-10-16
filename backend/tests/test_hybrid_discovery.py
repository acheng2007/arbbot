"""Cross-category retrieval, current validity, and public discovery workflow."""

import json
from datetime import timedelta
from pathlib import Path

import httpx
from sqlalchemy import select, update

from arbbot.api.app import create_app
from arbbot.config import Settings
from arbbot.discovery.inventory import CatalogInventory
from arbbot.exchanges.base import ExchangeHTTP
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.matching.classification import ClassificationService
from arbbot.matching.classification_provider import DecisionsProvider, RecordedDecisions
from arbbot.matching.retrieval import HybridRetriever, content_hash, semantic_pairs
from arbbot.matching.service import match_markets, retrieve_candidates
from arbbot.storage.models import EmbeddingRecord, MatchRecord
from tests.test_classification import prepared, response

ROOT = Path(__file__).parent / "fixtures/discovery_broad"


def authentic_markets():
    records = json.loads((ROOT / "recorded.json").read_text(), parse_float=str)["markets"]
    markets = []
    for record in records:
        adapter = KalshiAdapter if record["venue"] == "kalshi" else PolymarketUSAdapter
        market = adapter.normalize_market(record["payload"])
        # Category comes from separately captured official series metadata.
        if "category" in record:
            market = market.model_copy(update={"category": record["category"]})
        markets.append(market)
    return markets


async def test_authentic_elections_enter_inventory_and_api(database):
    settings, db, repo = database
    settings = settings.model_copy(
        update={
            "mode": "live",
            "discovery_mode": "broad",
            "enabled_venues": ("kalshi", "polymarket_us"),
        }
    )
    records = json.loads((ROOT / "recorded.json").read_text())["markets"]
    rows = [r["payload"] for r in records if r["venue"] == "polymarket_us"]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"markets": rows}))
    ) as network:
        adapter = PolymarketUSAdapter(ExchangeHTTP(network, interval=0))
        await CatalogInventory(settings, repo).scan(adapter)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as api:
        observed = (
            await api.get("/api/v1/market-summaries", params={"category_group": "politics"})
        ).json()
        assert len(observed) == 4
        assert all(m["category_group"] == "politics" for m in observed)
        assert all(m["venue"] == "polymarket_us" for m in observed)


def test_mixed_authentic_catalog_has_no_family_admission_gate():
    markets = authentic_markets()
    assert {m.category_group for m in markets} == {"politics", "economics", "sports", "other"}
    pairs, _ = retrieve_candidates(markets, {}, [])
    keys = {tuple(sorted((a.id, b.id))) for a, b in pairs}
    labels = json.loads((ROOT / "labels.json").read_text())["pairs"]
    # Recall for these supplied political propositions, not settlement correctness.
    for pair in labels:
        if pair["event_label"] == "same_event":
            assert tuple(sorted((pair["left_id"], pair["right_id"]))) in keys


async def test_low_score_suggestion_visible_without_qualification(database, fixture_market):
    markets, _, settings, service, job = await prepared(database, fixture_market)
    settings = settings.model_copy(update={"enabled_venues": tuple(m.venue for m in markets)})
    reply = response(job.request)
    reply["answers"]["event"].update(
        confidence=0.1,
        probabilities={
            "same_event": 0.4,
            "different_event": 0.3,
            "insufficient_evidence": 0.3,
        },
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=reply))
    ) as network:
        service.provider = DecisionsProvider(network, "offline")
        await service.process(job.key)
    advice = await service.advice("live")
    matches = match_markets(markets, [], classifications=advice)
    assert len(matches) == 1 and matches[0].relationship == "unverified"
    await database[2].publish("live", matches, [])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, database[1])), base_url="http://test"
    ) as api:
        page = (
            await api.get(
                "/api/v1/matches",
                params={
                    "relationship": "unverified",
                    "classification": "suggested",
                    "limit": 1,
                },
            )
        ).json()
        assert len(page) == 1 and page[0]["classification"]["event"]["confidence"] == 0.1
        assert not (await api.get("/api/v1/opportunities")).json()
        coverage = (await api.get("/api/v1/discovery/coverage")).json()
        assert coverage["unverified"] == 1 and coverage["contracts"] == 2
        assert coverage["verified"] == 0


def test_lexical_and_semantic_search_ignore_category_and_close_date(fixture_market):
    left, right = fixture_market[0]
    left = left.model_copy(
        update={"title": "Election chamber control", "rules": "", "category": "Elections"}
    )
    right = right.model_copy(
        update={
            "title": "Election chamber control",
            "rules": "",
            "category": "World",
            "closes_at": left.closes_at + timedelta(days=90),
        }
    )
    assert len(retrieve_candidates([left, right], {}, [])[0]) == 1
    right = right.model_copy(update={"title": "Completely different wording"})
    vectors = {left.id: [1, 0], right.id: [1, 0]}
    assert semantic_pairs([left, right], vectors) == {tuple(sorted((left.id, right.id)))}


class CountingEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(texts)
        return [[1.0, *([0.0] * 383)] for text in texts]


async def test_embedding_cache_restart_invalidation_and_failure(database, fixture_market):
    settings, db, repo = database
    settings = settings.model_copy(update={"mode": "live"})
    markets = [m.model_copy(update={"mode": "live"}) for m in fixture_market[0]]
    for market in markets:
        await repo.save_market(market)
    encoder = CountingEncoder()
    retriever = HybridRetriever(settings, db, encoder=encoder)
    await retriever.refresh(markets)
    assert len(encoder.calls) == 1 and retriever.current_pairs(markets)
    restarted = HybridRetriever(settings, db, encoder=encoder)
    await restarted.refresh(markets)
    assert len(encoder.calls) == 1
    changed = markets[0].model_copy(update={"rules": "A changed event definition"})
    assert content_hash(changed) != content_hash(markets[0])
    assert not restarted.current_pairs([changed, markets[1]])
    await repo.save_market(changed)
    await restarted.refresh([changed, markets[1]])
    assert len(encoder.calls) == 2
    async with db.sessions() as session:
        assert len((await session.scalars(select(EmbeddingRecord))).all()) == 3

    def fail(texts):
        raise RuntimeError("secret provider response must not leak")

    encoder.encode = fail
    another = changed.model_copy(update={"rules": "Another change"})
    await repo.save_market(another)
    await restarted.refresh([another, markets[1]])
    assert not restarted.current_pairs([another, markets[1]])
    assert retrieve_candidates([another, markets[1]], {}, [])[0]


async def test_withdrawn_pair_has_explicit_history(database, fixture_market):
    settings, db, repo = database
    markets, _, _, match = fixture_market
    for m in markets:
        await repo.save_market(m)
    await repo.publish(settings.mode, [match], [])
    async with db.sessions.begin() as session:
        await session.execute(
            update(MatchRecord).where(MatchRecord.id == match.id).values(current=False)
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as api:
        assert (await api.get(f"/api/v1/matches/{match.id}")).status_code == 404
        archived_response = await api.get(
            f"/api/v1/matches/{match.id}", params={"historical": True}
        )
        assert archived_response.status_code == 200, archived_response.text
        archived = archived_response.json()
        assert archived["historical"] and archived["relationship"] == "unverified"
        assert len((await api.get("/api/v1/matches", params={"historical": True})).json()) == 1


async def test_coverage_keeps_provider_and_venue_health_separate(database, fixture_market):
    settings, db, repo = database
    for market in fixture_market[0]:
        await repo.save_market(market)
    await repo.set_health(settings.mode, fixture_market[0][0].venue, "healthy", 1, 0)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as api:
        result = await api.get("/api/v1/discovery/coverage")
        assert result.status_code == 200
        assert result.json()["model_state"] == "disabled"


async def test_actual_low_score_provider_capture_is_visible_and_input_bound(database):
    _, db, repo = database
    path = ROOT / "jev-captured.json"
    recording = json.loads(path.read_text())
    pair = next(iter(recording["pairs"]))
    ids = pair.split("|")
    markets = [m for m in authentic_markets() if m.id in ids]
    for market in markets:
        await repo.save_market(market)
    settings = Settings(_env_file=None, mode="live", classification_recording_file=path)
    service = ClassificationService(settings, db)
    await service.schedule(markets)
    from arbbot.storage.models import ClassificationJobRecord

    async with db.sessions() as session:
        job = await session.scalar(select(ClassificationJobRecord))
    replay = RecordedDecisions(path)
    async with httpx.AsyncClient(transport=replay.transport) as client:
        service.provider = DecisionsProvider(client, "offline")
        await service.process(job.key)
    advice = await service.advice("live")
    value = advice[job.match_id]
    assert value.state == "fresh" and value.supports_candidate
    assert value.event.confidence == 0.76  # Actual observed score, not a scripted answer.
    assert value.outcome_relation.choice == "different_outcomes"
    matches = match_markets(markets, [], classifications=advice)
    assert len(matches) == 1 and matches[0].relationship == "unverified"
    # A capture cannot silently be rebound to modified source text.
    body = json.loads(json.dumps(recording["requests"][pair]))
    body["state"]["markets"][0]["title"] = "Different underlying event"
    request = httpx.Request("POST", "https://openrouter.ai/api/alpha/decisions", json=body)
    assert replay.handle(request).status_code == 422
