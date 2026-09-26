import httpx
import pytest

from arbbot.api.app import create_app
from arbbot.domain import utcnow
from arbbot.ingestion.pipeline import Pipeline
from arbbot.reviews.models import Actor, DecisionWrite, DraftWrite
from arbbot.reviews.repository import ReviewRepository
from arbbot.sources.models import SourceCapture, SourceFailure
from arbbot.sources.repository import SourceRepository
from tests.test_contracts import definition, live_pair

ACTOR = Actor(issuer="https://identity.example.test/", subject="fixture-reviewer")


@pytest.fixture
async def reviewed_pipeline(database, fixture_market):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live"})
    markets, books, review, _ = live_pair(fixture_market)
    reviews, sources = ReviewRepository(db), SourceRepository(db)
    drafts, captures = [], []
    for index, market in enumerate(markets):
        market = market.model_copy(update={"settlement_details": {"source_status": "captured"}})
        markets[index] = market
        await repository.save_market(market)
        capture = SourceCapture(
            venue=market.venue,
            mode="live",
            market_id=market.id,
            url=f"https://example.test/{market.venue}/terms",
            label="contract_terms",
            content=market.rules.encode(),
            content_type="text/plain",
            retrieved_at=utcnow(),
        )
        captures.append(capture)
        artifact = await sources.record(capture)
        drafts.append(
            await reviews.save_draft(
                "live",
                market.id,
                DraftWrite(
                    definition=definition(market),
                    source_artifact_ids=(artifact.id,),
                    reason="Review synthetic source evidence for pipeline test",
                ),
                ACTOR,
            )
        )
    review = review.model_copy(
        update={
            "left_terms_hash": markets[0].terms_hash,
            "right_terms_hash": markets[1].terms_hash,
            "left_definition_hash": drafts[0].definition_hash,
            "right_definition_hash": drafts[1].definition_hash,
        }
    )
    request = DecisionWrite(
        left_draft_id=drafts[0].id,
        right_draft_id=drafts[1].id,
        action="verified",
        reason="Approve synthetic pipeline fixture",
        review=review,
    )

    class Adapter:
        def __init__(self, market):
            self.market, self.venue = market, market.venue

        async def discover(self, limit):
            return [self.market]

        async def fetch_book(self, market):
            return books[market.id]

    pipeline = Pipeline(settings, repository, [Adapter(m) for m in markets])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        yield pipeline, reviews, request, drafts, sources, captures, client


@pytest.mark.parametrize("action", ["revoked", "rejected"])
async def test_database_approval_and_revocation_control_worker_and_api(reviewed_pipeline, action):
    pipeline, reviews, request, _, _, _, client = reviewed_pipeline
    assert (await pipeline.cycle())["opportunities"] == 0
    approved = await reviews.save_decision("live", request, ACTOR)
    assert (await pipeline.cycle())["opportunities"] == 1
    opportunity = (await client.get("/api/v1/opportunities")).json()[0]
    assert opportunity["review_revision_id"] == approved.id
    await reviews.save_decision(
        "live",
        request.model_copy(
            update={
                "expected_revision_id": approved.id,
                "action": action,
                "review": None,
            }
        ),
        ACTOR,
    )
    assert (await client.get("/api/v1/opportunities")).json() == []
    status = "rejected" if action == "rejected" else "candidate"
    matches = await client.get("/api/v1/matches", params={"status": status, "limit": 1})
    assert matches.json()[0]["status"] == status
    assert (await client.get("/api/v1/matches", params={"status": "verified"})).json() == []
    assert (await pipeline.repository.opportunities("live", 120, history=True))[
        0
    ].review_revision_id == approved.id
    assert (await pipeline.cycle())["opportunities"] == 0


@pytest.mark.parametrize("change", ["draft", "source", "terms"])
async def test_evidence_changes_hide_persisted_opportunities_immediately(reviewed_pipeline, change):
    pipeline, reviews, request, drafts, sources, captures, client = reviewed_pipeline
    await reviews.save_decision("live", request, ACTOR)
    assert (await pipeline.cycle())["opportunities"] == 1
    if change == "draft":
        old = drafts[0]
        await reviews.save_draft(
            "live",
            old.market.id,
            DraftWrite(
                expected_revision_id=old.id,
                definition=old.definition,
                source_artifact_ids=old.source_artifact_ids,
                reason="Reopen the reviewed interpretation",
            ),
            ACTOR,
        )
    elif change == "source":
        capture = captures[0]
        await sources.record(
            SourceFailure(
                venue=capture.venue,
                mode=capture.mode,
                market_id=capture.market_id,
                url=capture.url,
                label=capture.label,
                reason="http_error",
                detail="source_http_503",
                attempted_at=utcnow(),
            )
        )
    else:
        await pipeline.repository.save_market(
            drafts[0].market.model_copy(
                update={
                    "rules": "The settlement policy has materially changed",
                    "observed_at": utcnow(),
                }
            )
        )
    assert (await client.get("/api/v1/opportunities")).json() == []


async def test_revocation_during_calculation_cannot_publish_stale_result(
    reviewed_pipeline, monkeypatch
):
    pipeline, reviews, request, _, _, _, client = reviewed_pipeline
    approved = await reviews.save_decision("live", request, ACTOR)
    publish = pipeline.repository.publish

    async def revoke_before_publish(mode, matches, evaluations):
        assert any(e.opportunities for e in evaluations)
        await reviews.save_decision(
            "live",
            request.model_copy(
                update={
                    "expected_revision_id": approved.id,
                    "action": "revoked",
                    "review": None,
                }
            ),
            ACTOR,
        )
        return await publish(mode, matches, evaluations)

    monkeypatch.setattr(pipeline.repository, "publish", revoke_before_publish)
    assert (await pipeline.cycle())["opportunities"] == 0
    assert (await client.get("/api/v1/opportunities")).json() == []
    evaluations = await pipeline.repository.evaluations("live")
    assert any("approval_changed_before_publication" in e["blocked_reasons"] for e in evaluations)


async def test_database_mode_never_falls_back_to_review_files(reviewed_pipeline, tmp_path):
    pipeline, _, _, _, _, _, _ = reviewed_pipeline
    path = tmp_path / "invalid.json"
    path.write_text("This must not be read in database mode")
    pipeline.settings = pipeline.settings.model_copy(
        update={"reviews_file": path, "definitions_file": path}
    )
    assert (await pipeline.cycle())["opportunities"] == 0


async def test_new_approval_requires_recalculation_instead_of_reviving_old_result(
    reviewed_pipeline,
):
    pipeline, reviews, request, _, _, _, client = reviewed_pipeline
    first = await reviews.save_decision("live", request, ACTOR)
    assert (await pipeline.cycle())["opportunities"] == 1
    second = await reviews.save_decision(
        "live",
        request.model_copy(
            update={
                "expected_revision_id": first.id,
            }
        ),
        ACTOR,
    )
    assert (await client.get("/api/v1/opportunities")).json() == []
    assert (await pipeline.cycle())["opportunities"] == 1
    assert (await client.get("/api/v1/opportunities")).json()[0]["review_revision_id"] == second.id


async def test_live_database_api_filters_unbound_legacy_results(reviewed_pipeline):
    from arbbot.domain import Evaluation

    pipeline, reviews, request, _, _, _, client = reviewed_pipeline
    await reviews.save_decision("live", request, ACTOR)
    assert (await pipeline.cycle())["opportunities"] == 1
    opportunity = (await pipeline.repository.opportunities("live", 120))[0]
    matches = await pipeline.repository.matches("live")
    unbound = opportunity.model_copy(update={"id": "legacy-result", "review_revision_id": None})
    await pipeline.repository.publish(
        "live",
        matches,
        [
            Evaluation(
                match_id=opportunity.match_id,
                mode="live",
                evaluated_at=utcnow(),
                blocked_reasons=(),
                opportunities=(unbound, opportunity),
            )
        ],
    )
    result = (await client.get("/api/v1/opportunities", params={"limit": 1})).json()
    assert [item["id"] for item in result] == [opportunity.id]
