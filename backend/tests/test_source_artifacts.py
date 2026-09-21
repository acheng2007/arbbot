from datetime import timedelta

import pytest
from pydantic import ValidationError

from arbbot.domain import utcnow
from arbbot.sources.models import (
    MAX_CONTENT_BYTES,
    SourceArtifact,
    SourceCapture,
    SourceFailure,
    bounded_capture,
)
from arbbot.sources.repository import SourceRepository

RULES_URL = "https://www.bls.gov/news.release/cpi.nr0.htm"
SERIES_URL = "https://api.elections.kalshi.com/trade-api/v2/series/KXCPI"


def capture(market, content=b"Original release rules", **overrides):
    fields = {
        "venue": market.venue,
        "mode": market.mode,
        "market_id": market.id,
        "url": RULES_URL,
        "label": "resolution_source",
        "content": content,
        "content_type": "text/html; charset=utf-8",
        "retrieved_at": utcnow(),
    }
    return SourceCapture(**(fields | overrides))


def failure(market, **overrides):
    fields = {
        "venue": market.venue,
        "mode": market.mode,
        "market_id": market.id,
        "url": RULES_URL,
        "label": "resolution_source",
        "reason": "http_error",
        "detail": "Publisher returned 503",
        "status_code": 503,
        "attempted_at": utcnow(),
    }
    return SourceFailure(**(fields | overrides))


@pytest.fixture
async def sources(database, fixture_market):
    _, db, repository = database
    markets, _, _, _ = fixture_market
    market = markets[0]
    await repository.save_market(market)
    return SourceRepository(db), repository, market


async def test_repeated_identical_capture_records_one_artifact(sources):
    store, _, market = sources
    first = await store.record(capture(market))
    later = utcnow() + timedelta(minutes=5)
    second = await store.record(capture(market, retrieved_at=later))

    assert second.id == first.id
    assert second.observations == 2
    assert second.first_seen_at == first.first_seen_at
    assert second.last_seen_at == later
    assert len(await store.artifacts(market.mode, market.id)) == 1


async def test_changed_source_preserves_the_previous_artifact(sources):
    store, _, market = sources
    original = await store.record(capture(market))
    changed = await store.record(
        capture(market, content=b"Revised release rules", retrieved_at=utcnow())
    )

    assert changed.id != original.id
    history = await store.artifacts(market.mode, market.id)
    assert [item.id for item in history] == [changed.id, original.id]
    assert history[1].content == b"Original release rules"
    assert history[1].content_digest == original.content_digest
    latest = await store.latest(market.mode, market.id, RULES_URL, "resolution_source")
    assert latest.id == changed.id


async def test_binary_content_survives_storage_and_json_transport(sources):
    store, _, market = sources
    content = bytes(range(256)) + b"\x00\xff"
    stored = await store.record(capture(market, content=content, content_type="application/pdf"))

    assert stored.content == content
    assert stored.byte_size == len(content)
    assert SourceArtifact.model_validate_json(stored.model_dump_json()) == stored


async def test_source_and_receipt_timestamps_stay_separate(sources):
    store, _, market = sources
    published = utcnow() - timedelta(hours=3)
    retrieved = utcnow()
    stored = await store.record(capture(market, source_at=published, retrieved_at=retrieved))

    assert stored.source_at == published
    assert stored.first_seen_at == retrieved


async def test_failed_retrieval_is_recorded_without_completing_evidence(sources):
    store, _, market = sources
    stored = await store.record(failure(market))

    assert stored.status == "failed"
    assert not stored.complete
    assert stored.content is None and stored.content_digest is None
    assert stored.reason == "http_error" and stored.status_code == 503
    assert await store.missing_evidence(market.mode, market.id, ["resolution_source"]) == [
        "resolution_source"
    ]


async def test_repeated_identical_failures_are_idempotent(sources):
    store, _, market = sources
    first = await store.record(failure(market))
    second = await store.record(failure(market, attempted_at=utcnow() + timedelta(minutes=1)))

    assert (second.id, second.observations) == (first.id, 2)
    assert len(await store.artifacts(market.mode, market.id)) == 1


async def test_a_later_failure_invalidates_previously_captured_evidence(sources):
    store, _, market = sources
    await store.record(capture(market))
    assert await store.missing_evidence(market.mode, market.id, ["resolution_source"]) == []

    await store.record(failure(market, attempted_at=utcnow() + timedelta(minutes=1)))
    assert await store.missing_evidence(market.mode, market.id, ["resolution_source"]) == [
        "resolution_source"
    ]


async def test_missing_evidence_reports_labels_that_were_never_captured(sources):
    store, _, market = sources
    await store.record(capture(market))
    missing = await store.missing_evidence(
        market.mode, market.id, ["resolution_source", "series_metadata"]
    )
    assert missing == ["series_metadata"]


async def test_changed_market_terms_invalidate_earlier_evidence(sources):
    store, repository, market = sources
    await store.record(capture(market))
    updated = market.model_copy(update={"rules": "New settlement terms", "observed_at": utcnow()})
    await repository.save_market(updated)

    assert (
        await store.missing_evidence(
            market.mode, market.id, ["resolution_source"], terms_hash=market.terms_hash
        )
        == []
    )
    assert await store.missing_evidence(
        market.mode, market.id, ["resolution_source"], terms_hash=updated.terms_hash
    ) == ["resolution_source"]


async def test_oversized_documents_are_recorded_as_failures(sources):
    store, _, market = sources
    oversized = bounded_capture(
        content=b"x" * 2048,
        limit=1024,
        venue=market.venue,
        mode=market.mode,
        market_id=market.id,
        url=RULES_URL,
        label="resolution_source",
        content_type="text/html",
        retrieved_at=utcnow(),
    )
    assert isinstance(oversized, SourceFailure)
    assert oversized.reason == "too_large"

    stored = await store.record(oversized)
    assert stored.status == "failed" and stored.byte_size == 0
    assert await store.missing_evidence(market.mode, market.id, ["resolution_source"]) == [
        "resolution_source"
    ]


async def test_documents_above_the_configured_limit_are_never_stored(sources):
    store, _, market = sources
    bounded = SourceRepository(store.database, max_content_bytes=1024)
    with pytest.raises(ValueError, match="exceeds"):
        await bounded.record(capture(market, content=b"x" * 2048))
    assert await bounded.artifacts(market.mode, market.id) == []

    with pytest.raises(ValidationError):
        capture(market, content=b"x" * (MAX_CONTENT_BYTES + 1))
    with pytest.raises(ValueError, match="limit"):
        SourceRepository(store.database, max_content_bytes=MAX_CONTENT_BYTES + 1)


async def test_evidence_requires_a_persisted_market_and_stays_mode_isolated(sources):
    store, _, market = sources
    await store.record(capture(market))

    with pytest.raises(ValueError, match="Market must be persisted"):
        await store.record(capture(market, market_id="unknown-market"))
    with pytest.raises(ValueError, match="Market must be persisted"):
        await store.record(capture(market, mode="live"))
    with pytest.raises(ValueError, match="must name the venue"):
        await store.record(capture(market, venue="polymarket"))
    assert await store.artifacts("live", market.id) == []


async def test_evidence_is_filtered_by_label_and_url(sources):
    store, _, market = sources
    await store.record(capture(market))
    series = await store.record(
        capture(
            market,
            url=SERIES_URL,
            label="series_metadata",
            content=b'{"series": "KXCPI"}',
            content_type="application/json",
        )
    )

    assert len(await store.artifacts(market.mode, market.id)) == 2
    by_label = await store.artifacts(market.mode, market.id, label="series_metadata")
    assert [item.id for item in by_label] == [series.id]
    by_url = await store.artifacts(market.mode, market.id, url=RULES_URL)
    assert [item.url for item in by_url] == [RULES_URL]


async def test_artifact_identity_rejects_unusable_references(sources):
    _, _, market = sources
    for url in ("/news.release/cpi.htm", "ftp://bls.gov/cpi", "bls.gov/cpi"):
        with pytest.raises(ValidationError):
            capture(market, url=url)
    with pytest.raises(ValidationError):
        capture(market, label="Resolution Source")
    with pytest.raises(ValidationError):
        failure(market, status_code=99)
