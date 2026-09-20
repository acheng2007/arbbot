import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from arbbot.domain import utcnow
from arbbot.sources.models import MAX_DOCUMENT_BYTES, SourceCapture
from arbbot.sources.repository import SourceRepository
from arbbot.storage.models import SourceArtifactRecord, SourceCaptureRecord


def capture_for(market, **overrides):
    return SourceCapture(
        **{
            "mode": market.mode,
            "market_id": market.id,
            "venue": market.venue,
            "url": "https://example.com/rules",
            "retrieved_at": utcnow(),
            "content_type": "application/pdf",
            "content": b"original terms",
            "http_status": 200,
            **overrides,
        }
    )


async def test_capture_versions_retries_and_failures(database, fixture_market):
    _, db, markets = database
    market = fixture_market[0][0]
    await markets.save_market(market)
    sources = SourceRepository(db)
    original = capture_for(market)
    assert await sources.capture(original) == await sources.capture(original)
    repeated = capture_for(market, retrieved_at=original.retrieved_at + timedelta(seconds=1))
    await asyncio.gather(*(sources.capture(repeated) for _ in range(4)))
    changed = capture_for(market, content=b"revised terms")
    await sources.capture(changed)
    failed = capture_for(market, content=None, failure="http_error", http_status=503)
    await sources.capture(failed)
    history = await sources.history(market.mode, market.id)
    assert len(history) == 4
    assert {c.content for c in history} == {b"original terms", b"revised terms", None}
    assert next(c for c in history if c.failure).artifact_id is None
    assert await sources.history("live", market.id) == []
    assert len(await sources.history(market.mode, market.id, limit=1, offset=1)) == 1
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SourceArtifactRecord)) == 2
        assert await session.scalar(select(func.count()).select_from(SourceCaptureRecord)) == 4


async def test_capture_rejects_wrong_association(database, fixture_market):
    _, db, markets = database
    market = fixture_market[0][0]
    sources = SourceRepository(db)
    with pytest.raises(ValueError, match="persisted market"):
        await sources.capture(capture_for(market))
    await markets.save_market(market)
    with pytest.raises(ValueError, match="same venue"):
        await sources.capture(capture_for(market, venue="polymarket"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"content": b"x" * (MAX_DOCUMENT_BYTES + 1)},
        {"content": b""},
        {"content": None},
        {"content_type": None},
        {"http_status": 404},
        {"failure": "timeout"},
        {"url": "https://user:password@example.com/rules"},
        {"url": "https://example.com/rules?token=secret"},
    ],
)
async def test_invalid_evidence_rejected(fixture_market, overrides):
    with pytest.raises(ValidationError):
        capture_for(fixture_market[0][0], **overrides)


async def test_oversized_retrieval_is_an_explicit_failure(database, fixture_market):
    _, db, markets = database
    market = fixture_market[0][0]
    await markets.save_market(market)
    sources = SourceRepository(db)
    await sources.capture(capture_for(market, content=None, failure="too_large"))
    result = (await sources.history(market.mode, market.id))[0]
    assert result.content is None and result.content_digest is None
    assert result.failure == "too_large"
