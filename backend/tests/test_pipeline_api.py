from datetime import timedelta

import httpx
from sqlalchemy import func, select, update

from arbbot.api.app import create_app
from arbbot.domain import utcnow
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.pipeline import Pipeline
from arbbot.storage.models import HealthRecord, OpportunityRecord, SnapshotRecord


def adapters():
    return [SimulationAdapter(venue) for venue in ("kalshi", "polymarket")]


async def test_ingestion_to_api_and_audit_history(database):
    settings, db, repository = database
    result = await Pipeline(settings, repository, adapters()).cycle()
    assert result == {
        "mode": "simulation",
        "markets": 2,
        "books": 2,
        "matches": 1,
        "opportunities": 1,
    }
    app = create_app(settings, db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/health/ready")).status_code == 200
        markets = (await client.get("/api/v1/markets")).json()
        assert len(markets) == 2
        assert markets[0]["mode"] == "simulation"
        assert len(markets[0]["terms_hash"]) == 64
        opportunities = (await client.get("/api/v1/opportunities")).json()
        assert opportunities[0]["net_profit"] == "1.61"
        assert len(opportunities[0]["legs"]) == 2
        assert (await client.get("/api/v1/markets/missing")).status_code == 404
        assert (await client.get("/api/v1/markets?limit=0")).status_code == 422
        assert (await client.get("/api/v1/status")).json()["ingestion_healthy"]
        assert "arbbot_http_requests_total" in (await client.get("/metrics")).text
        schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/opportunities" in schema["paths"]
        # A subsequent cycle replaces the active view, not the audit history.
        await Pipeline(settings, repository, adapters()).cycle()
        assert len((await client.get("/api/v1/opportunities")).json()) == 1
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 2

        assert len((await client.get("/api/v1/evaluations")).json()) == 1
        assert len((await client.get("/api/v1/evaluations?history=true")).json()) == 2
        async with db.sessions.begin() as session:
            await session.execute(
                update(OpportunityRecord).values(valid_until=utcnow() - timedelta(seconds=1))
            )
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 2


async def test_exact_opportunity_reports_input_changes_and_preserves_history(database):
    settings, db, repository = database
    pipeline = Pipeline(settings, repository, adapters())
    await pipeline.cycle()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        opportunity = (await client.get("/api/v1/opportunities")).json()[0]
        path = "/api/v1/opportunities/" + opportunity["id"]
        current = (await client.get(path)).json()
        assert current["status"] == "eligible" and current["invalidation_reasons"] == []
        await pipeline.cycle()
        previous = (await client.get(path)).json()
        assert previous["status"] == "invalidated" and not previous["eligible"]
        assert "evaluation_superseded_or_withdrawn" in previous["invalidation_reasons"]
        assert any(r.startswith("quote_changed:") for r in previous["invalidation_reasons"])
        assert previous["opportunity"] == opportunity
        await repository.set_health(settings.mode, "polymarket", "degraded", error="ReadTimeout")
        newest = (await client.get("/api/v1/opportunities/history")).json()[0]
        failed = (await client.get("/api/v1/opportunities/" + newest["id"])).json()
        assert failed["status"] == "invalidated"
        assert "venue_feed_unavailable:polymarket" in failed["invalidation_reasons"]


async def test_failed_exchange_invalidates_feed_and_recovers(database):
    settings, db, repository = database
    await Pipeline(settings, repository, adapters()).cycle()

    class FailingAdapter(SimulationAdapter):
        async def fetch_book(self, market):
            raise httpx.ReadTimeout("secret should never be returned")

    result = await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), FailingAdapter("polymarket")]
    ).cycle()
    assert result["opportunities"] == 0
    assert not await repository.opportunities(settings.mode, 120)
    health = await repository.health(settings.mode, 120)
    assert health[1]["error"] == "ReadTimeout"
    assert health[1]["status"] == "degraded"
    await Pipeline(settings, repository, adapters()).cycle()
    assert len(await repository.opportunities(settings.mode, 120)) == 1


async def test_stopped_worker_suppresses_feed(database):
    settings, db, repository = database
    await Pipeline(settings, repository, adapters()).cycle()
    async with db.sessions.begin() as session:
        await session.execute(
            update(HealthRecord).values(checked_at=utcnow() - timedelta(minutes=5))
        )
    assert not await repository.opportunities(settings.mode, 120)
    assert all(row["status"] == "stale" for row in await repository.health(settings.mode, 120))


async def test_snapshot_idempotency_and_out_of_order(database, fixture_market):
    _, db, repository = database
    markets, books, _, _ = fixture_market
    market = markets[0]
    book = books[market.id]
    await repository.save_market(market)
    assert await repository.save_book(book)
    assert await repository.save_book(book)
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SnapshotRecord)) == 1
    older = book.model_copy(
        update={
            "source_at": book.source_at - timedelta(seconds=1),
            "received_at": book.received_at + timedelta(seconds=1),
        }
    )
    assert not await repository.save_book(older)
    assert (await repository.book("simulation", market.id)).id == book.id


async def test_simulation_cannot_leak_into_live_api(database):
    settings, db, repository = database
    await Pipeline(settings, repository, adapters()).cycle()
    app = create_app(settings.model_copy(update={"mode": "live"}), db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/markets")).json() == []
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert (await client.get("/api/v1/status")).json()["mode"] == "live"
