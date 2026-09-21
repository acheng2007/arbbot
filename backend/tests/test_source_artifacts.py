import asyncio
from datetime import timedelta
from hashlib import sha256

import pytest
from pydantic import ValidationError

from arbbot.domain import utcnow
from arbbot.sources.models import MAX_CONTENT_BYTES, SourceCapture
from arbbot.sources.repository import SourceRepository


def capture(market, **changes):
    return SourceCapture.model_validate(
        dict(
            mode=market.mode,
            market_id=market.id,
            venue=market.venue,
            url="https://example.com/settlement.pdf",
            retrieved_at=utcnow(),
            status="success",
            content=b"%PDF-1.7\x00\xff recorded rules",
            content_type="application/pdf",
        )
        | changes
    )


@pytest.fixture
async def sources(database, fixture_market):
    _, db, repository = database
    markets, *_ = fixture_market
    for market in markets:
        await repository.save_market(market)
    return SourceRepository(db), markets[0], markets[1]


async def test_versions_and_repeat_captures_preserve_original_evidence(sources):
    repository, market, _ = sources
    original = capture(market)
    saved = await repository.save(original)
    later = capture(market, retrieved_at=original.retrieved_at + timedelta(seconds=5))
    assert await repository.save(later) == saved
    updated = capture(market, content=b"Revised settlement terms")
    await repository.save(updated)
    history = await repository.history(market.mode, market.id)
    assert len(history) == 2
    assert {item.content for item in history} == {original.content, updated.content}
    assert saved.content_digest == sha256(original.content).hexdigest()
    assert saved.retrieved_at == original.retrieved_at


async def test_concurrent_duplicate_writes_are_idempotent(sources):
    repository, market, _ = sources
    item = capture(market)
    results = await asyncio.gather(*(repository.save(item) for _ in range(5)))
    assert all(result == item for result in results)
    assert len(await repository.history(market.mode, market.id)) == 1


async def test_failures_remain_explicit_and_do_not_overwrite_evidence(sources):
    repository, market, _ = sources
    original = capture(market)
    await repository.save(original)
    failed = capture(
        market, status="failure", content=None, content_type=None, error="response_too_large"
    )
    await repository.save(failed)
    await repository.save(failed)
    later_failure = capture(
        market,
        status="failure",
        content=None,
        content_type=None,
        error="timeout",
        retrieved_at=failed.retrieved_at + timedelta(seconds=5),
    )
    await repository.save(later_failure)
    history = await repository.history(market.mode, market.id)
    assert len(history) == 3
    assert history[0].status == "failure"
    assert history[0].content_digest is None
    assert history[-1] == original


async def test_market_mode_venue_and_url_boundaries(sources):
    repository, market, other = sources
    item = capture(market)
    await repository.save(item)
    await repository.save(capture(other))
    await repository.save(capture(market, url="https://example.com/other.pdf"))
    assert len(await repository.history(market.mode, market.id)) == 2
    assert len(await repository.history(other.mode, other.id)) == 1
    assert await repository.history("live", market.id) == []
    for changes in ({"mode": "live"}, {"venue": other.venue}, {"market_id": "missing"}):
        with pytest.raises(ValueError, match="persisted market"):
            await repository.save(capture(market, **changes))
    with pytest.raises(ValueError, match="pagination"):
        await repository.history(market.mode, market.id, limit=201)
    first = await repository.history(market.mode, market.id, limit=1)
    second = await repository.history(market.mode, market.id, limit=1, offset=1)
    assert first[0].id != second[0].id


@pytest.mark.parametrize(
    "changes",
    [
        {"content": b"x" * (MAX_CONTENT_BYTES + 1)},
        {"content": b""},
        {"content_type": None},
        {"error": "timeout"},
        {"status": "failure"},
        {"status": "failure", "content": None, "content_type": None, "error": ""},
        {"url": "file:///etc/passwd"},
        {"url": "https://user:password@example.com/rules"},
        {"retrieved_at": "2026-01-01T00:00:00"},
    ],
)
async def test_invalid_captures_rejected(sources, changes):
    _, market, _ = sources
    with pytest.raises(ValidationError):
        capture(market, **changes)


async def test_persistence_revalidates_copied_models(sources):
    repository, market, _ = sources
    item = capture(market).model_copy(update={"content": b"x" * (MAX_CONTENT_BYTES + 1)})
    with pytest.raises(ValidationError):
        await repository.save(item)
    assert await repository.history(market.mode, market.id) == []


def test_source_migration_round_trip_preserves_existing_markets(tmp_path, monkeypatch):
    import sqlite3
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[1]
    path = tmp_path / "migration.db"
    monkeypatch.setenv("ARBBOT_DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "a2a3099f82df")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO markets (key, id, mode, venue, payload, observed_at) "
            "VALUES ('simulation:test', 'test', 'simulation', 'kalshi', '{}', '2026-01-01')"
        )
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO source_artifacts "
            "(id, market_key, retrieved_at, content_digest, content, payload) "
            "VALUES ('test', 'simulation:test', '2026-01-01', NULL, NULL, '{}')"
        )
    command.downgrade(config, "a2a3099f82df")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM markets").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'source_artifacts'"
            ).fetchone()
            is None
        )
    command.upgrade(config, "head")
    command.check(config)
