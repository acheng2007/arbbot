import asyncio
from datetime import timedelta

import pytest

from arbbot.domain import utcnow
from arbbot.matching.contracts import definition_hash
from arbbot.reviews.models import (
    Actor,
    DecisionWrite,
    DraftWrite,
    ReviewValidationError,
    RevisionConflict,
)
from arbbot.reviews.repository import ReviewRepository
from arbbot.sources.models import SourceCapture, SourceFailure
from arbbot.sources.repository import SourceRepository
from tests.test_catalog_migration import migrate
from tests.test_contracts import definition

ACTOR = Actor(issuer="https://issuer.example.test/", subject="reviewer-a")
OTHER = Actor(issuer="https://issuer.example.test/", subject="reviewer-b")


@pytest.fixture
async def drafts(database, fixture_market):
    _, db, repository = database
    markets, _, review, _ = fixture_market
    store = ReviewRepository(db)
    source_store = SourceRepository(db)
    saved, captures = [], []
    for market in markets:
        market = market.model_copy(
            update={"mode": "live", "settlement_details": {"source_status": "captured"}}
        )
        await repository.save_market(market)
        capture = SourceCapture(
            venue=market.venue,
            mode="live",
            market_id=market.id,
            url=f"https://evidence.example.test/{market.venue}/terms",
            label="contract_terms",
            content=market.rules.encode(),
            content_type="text/plain",
            retrieved_at=utcnow(),
        )
        artifact = await source_store.record(capture)
        captures.append(capture)
        saved.append(
            await store.save_draft(
                "live",
                market.id,
                DraftWrite(
                    definition=definition(market),
                    source_artifact_ids=(artifact.id,),
                    reason="Initial evidence interpretation",
                ),
                ACTOR,
            )
        )
    review = review.model_copy(
        update={
            "left_terms_hash": saved[0].market.terms_hash,
            "right_terms_hash": saved[1].market.terms_hash,
            "left_definition_hash": saved[0].definition_hash,
            "right_definition_hash": saved[1].definition_hash,
        }
    )
    request = DecisionWrite(
        left_draft_id=saved[0].id,
        right_draft_id=saved[1].id,
        action="verified",
        reason="Reviewed both definitions and source terms",
        review=review,
    )
    return store, saved, request, source_store, captures


async def test_revision_history_reconstructs_exact_evidence_and_actor(drafts):
    store, saved, request, _, _ = drafts
    decision = await store.save_decision("live", request, ACTOR)
    assert decision.review.reviewer == ACTOR.audit_id
    assert decision.review.reviewer != request.review.reviewer
    state = await store.current_decision("live", request.review.right_id, request.review.left_id)
    assert state.eligible and state.revision == decision
    assert state.revision.created_at.tzinfo
    old = await store.draft_revision("live", decision.left_draft_id)
    assert old == saved[0]
    assert old.definition_hash == definition_hash(old.definition)
    assert old.market.terms_hash == old.definition.terms_hash
    assert old.actor == ACTOR
    assert await store.decision_history("simulation", old.market.id, saved[1].market.id) == []
    with pytest.raises(LookupError):
        await store.draft_revision("simulation", old.id)


async def test_concurrent_draft_edits_do_not_overwrite_or_leave_orphan_revisions(drafts):
    store, saved, _, _, _ = drafts
    original = saved[0]
    writes = [
        DraftWrite(
            expected_revision_id=original.id,
            definition=original.definition.model_copy(update={"extractor": name}),
            source_artifact_ids=original.source_artifact_ids,
            reason="A concurrent edit of the draft",
        )
        for name in ("editor-a", "editor-b")
    ]
    results = await asyncio.gather(
        *(
            store.save_draft("live", original.market.id, write, actor)
            for write, actor in zip(writes, (ACTOR, OTHER), strict=True)
        ),
        return_exceptions=True,
    )
    conflicts = [result for result in results if isinstance(result, RevisionConflict)]
    assert len(conflicts) == 1, results
    history = await store.draft_history("live", original.market.id)
    assert len(history) == 2
    assert history[-1] == original
    assert history[0].previous_revision_id == original.id
    assert history[0].revision == 2
    assert conflicts[0].current_revision_id == history[0].id
    assert await store.current_draft("live", original.market.id) == history[0]


async def test_concurrent_initial_draft_creation_has_one_winner(database, fixture_market):
    _, db, repository = database
    market = fixture_market[0][0]
    await repository.save_market(market)
    store = ReviewRepository(db)
    write = DraftWrite(definition=definition(market), reason="Create a first definition draft")
    results = await asyncio.gather(
        *(store.save_draft("simulation", market.id, write, actor) for actor in (ACTOR, OTHER)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, RevisionConflict) for result in results) == 1, results
    assert len(await store.draft_history("simulation", market.id)) == 1


async def test_concurrent_decisions_have_one_winner_and_complete_history(drafts):
    store, saved, request, _, _ = drafts
    results = await asyncio.gather(
        store.save_decision("live", request, ACTOR),
        store.save_decision(
            "live",
            DecisionWrite(
                left_draft_id=saved[0].id,
                right_draft_id=saved[1].id,
                action="rejected",
                reason="Reject the proposed equivalence",
            ),
            OTHER,
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, RevisionConflict) for result in results) == 1, results
    assert len(await store.decision_history("live", saved[0].market.id, saved[1].market.id)) == 1


async def test_changed_draft_revokes_eligibility_but_preserves_historical_approval(drafts):
    store, saved, request, _, _ = drafts
    decision = await store.save_decision("live", request, ACTOR)
    await store.save_draft(
        "live",
        saved[0].market.id,
        DraftWrite(
            expected_revision_id=saved[0].id,
            definition=saved[0].definition,
            source_artifact_ids=saved[0].source_artifact_ids,
            reason="Reopen draft for another interpretation",
        ),
        OTHER,
    )
    state = await store.current_decision("live", saved[0].market.id, saved[1].market.id)
    assert not state.eligible and "left:draft_changed" in state.blocked_reasons
    assert state.revision == decision
    with pytest.raises(RevisionConflict) as caught:
        await store.save_decision(
            "live", request.model_copy(update={"expected_revision_id": decision.id}), ACTOR
        )
    assert "left:draft_changed" in caught.value.issues


async def test_changed_market_terms_and_expiry_invalidate_without_erasing_history(
    drafts, database, monkeypatch
):
    store, saved, request, _, _ = drafts
    _, _, repository = database
    decision = await store.save_decision("live", request, ACTOR)
    await repository.save_market(
        saved[0].market.model_copy(
            update={"rules": "Changed publication policy", "observed_at": utcnow()}
        )
    )
    monkeypatch.setattr(
        "arbbot.reviews.repository.utcnow",
        lambda: decision.review.expires_at + timedelta(seconds=1),
    )
    state = await store.current_decision("live", saved[0].market.id, saved[1].market.id)
    assert not state.eligible
    assert set(state.blocked_reasons) == {"approval_expired", "left:market_terms_changed"}
    assert (await store.draft_revision("live", saved[0].id)).market.rules == saved[0].market.rules


@pytest.mark.parametrize("failure", [False, True])
async def test_changed_or_failed_source_invalidates_approval(drafts, failure):
    store, saved, request, sources, captures = drafts
    decision = await store.save_decision("live", request, ACTOR)
    capture = captures[0]
    if failure:
        await sources.record(
            SourceFailure(
                venue=capture.venue,
                mode=capture.mode,
                market_id=capture.market_id,
                url=capture.url,
                label=capture.label,
                reason="http_error",
                detail="source_http_503",
                status_code=503,
                attempted_at=utcnow(),
            )
        )
    else:
        await sources.record(
            capture.model_copy(
                update={"content": b"Changed source terms", "retrieved_at": utcnow()}
            )
        )
    state = await store.current_decision("live", saved[0].market.id, saved[1].market.id)
    assert not state.eligible
    assert f"left:source_changed:{saved[0].source_artifact_ids[0]}" in state.blocked_reasons
    if not failure:
        assert "left:source_revision_changed" in state.blocked_reasons
    assert state.revision == decision


async def test_rejection_and_revocation_preserve_decisions_and_expected_revision(drafts):
    store, saved, request, _, _ = drafts
    approved = await store.save_decision("live", request, ACTOR)
    revoked = await store.save_decision(
        "live",
        DecisionWrite(
            expected_revision_id=approved.id,
            left_draft_id=saved[0].id,
            right_draft_id=saved[1].id,
            action="revoked",
            reason="New exceptional condition needs review",
        ),
        OTHER,
    )
    state = await store.current_decision("live", saved[0].market.id, saved[1].market.id)
    assert not state.eligible and state.blocked_reasons == ("review_revoked",)
    assert revoked.previous_revision_id == approved.id and revoked.actor == OTHER
    assert await store.decision_history("live", saved[0].market.id, saved[1].market.id) == [
        revoked,
        approved,
    ]
    with pytest.raises(RevisionConflict) as caught:
        await store.save_decision(
            "live", request.model_copy(update={"expected_revision_id": approved.id}), ACTOR
        )
    assert caught.value.current_revision_id == revoked.id


async def test_wrong_evidence_mode_or_hash_and_incomplete_definitions_cannot_be_approved(drafts):
    store, saved, request, _, _ = drafts
    with pytest.raises(LookupError):
        await store.save_decision("simulation", request, ACTOR)
    with pytest.raises(RevisionConflict):
        await store.save_decision(
            "live",
            request.model_copy(
                update={
                    "review": request.review.model_copy(update={"left_definition_hash": "0" * 64})
                }
            ),
            ACTOR,
        )
    with pytest.raises(ReviewValidationError):
        await store.save_draft(
            "live",
            saved[0].market.id,
            DraftWrite(
                expected_revision_id=saved[0].id,
                definition=saved[0].definition,
                source_artifact_ids=saved[1].source_artifact_ids,
                reason="Wrong venue source must be rejected",
            ),
            ACTOR,
        )
    changed = await store.save_draft(
        "live",
        saved[0].market.id,
        DraftWrite(
            expected_revision_id=saved[0].id,
            definition=saved[0].definition.model_copy(update={"facts": {}}),
            reason="Incomplete draft is allowed for editing",
        ),
        ACTOR,
    )
    with pytest.raises(ReviewValidationError):
        await store.save_decision(
            "live",
            request.model_copy(
                update={
                    "left_draft_id": changed.id,
                    "review": request.review.model_copy(
                        update={"left_definition_hash": changed.definition_hash}
                    ),
                }
            ),
            ACTOR,
        )


async def test_live_review_write_rejects_implicit_payouts(drafts):
    store, _, request, _, _ = drafts
    implicit = request.review.model_copy(
        update={
            "scenarios": tuple(
                s.model_copy(update={"left_no": None, "right_no": None})
                for s in request.review.scenarios
            )
        }
    )
    with pytest.raises(ReviewValidationError) as caught:
        await store.save_decision("live", request.model_copy(update={"review": implicit}), ACTOR)
    assert {
        f"explicit_settlement_payouts_required:{scenario.name}" for scenario in implicit.scenarios
    }.issubset(caught.value.issues)


async def test_review_migration_preserves_existing_sources_and_catalog(database, fixture_market):
    from arbbot.discovery.models import CatalogReport
    from arbbot.discovery.service import catalog_reports
    from arbbot.storage.models import Base, CatalogRecord

    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "b005_discovery_catalogs")
    market = fixture_market[0][0]
    await repository.save_market(market)
    sources = SourceRepository(db)
    evidence = await sources.record(
        SourceCapture(
            venue=market.venue,
            mode=market.mode,
            market_id=market.id,
            url="https://example.test/settlement",
            label="contract_terms",
            content=b"Recorded settlement evidence before review migration",
            content_type="text/plain",
            retrieved_at=utcnow(),
        )
    )
    now = utcnow()
    report = CatalogReport(
        mode=market.mode,
        venue=market.venue,
        status="ready",
        started_at=now,
        completed_at=now,
        valid_until=now + timedelta(hours=1),
        selected_market_ids=(market.id,),
        decisions=(),
        pages_scanned=1,
        truncated=False,
    )
    async with db.sessions.begin() as session:
        session.add(
            CatalogRecord(
                key=f"{market.mode}:{market.venue}",
                mode=market.mode,
                venue=market.venue,
                payload=report.model_dump(mode="json"),
            )
        )
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    store = ReviewRepository(db)
    draft = await store.save_draft(
        "simulation",
        market.id,
        DraftWrite(definition=definition(market), reason="Verify the migrated draft storage"),
        ACTOR,
    )
    assert await store.current_draft("simulation", market.id) == draft
    assert await repository.market("simulation", market.id) == market
    assert await sources.artifacts(market.mode, market.id) == [evidence]
    assert await catalog_reports(db, market.mode) == [report]
    await migrate(settings, "downgrade", "b005_discovery_catalogs")
    assert await repository.market("simulation", market.id) == market
    assert await sources.artifacts(market.mode, market.id) == [evidence]
    assert await catalog_reports(db, market.mode) == [report]
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")


async def test_per_venue_cancellation_coverage_is_not_joint_settlement_proof(drafts):
    store, _, request, _, _ = drafts
    incomplete = request.model_copy(
        update={"review": request.review.model_copy(update={"joint_settlement_cases": ()})}
    )
    with pytest.raises(ReviewValidationError) as error:
        await store.save_decision("live", incomplete, ACTOR)
    assert any("joint_settlement_case_uncovered" in issue for issue in error.value.issues)
