"""User-facing ingestion regressions, exercised through persistence and the API."""

from datetime import timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from arbbot.api.app import create_app
from arbbot.domain import Evaluation, Opportunity, utcnow
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.pipeline import Pipeline
from arbbot.storage.models import OpportunityRecord


class PartialFailureAdapter(SimulationAdapter):
    async def discover(self, limit):
        good = (await super().discover(limit))[0]
        bad = good.model_copy(update={"id": "kalshi:UNAVAILABLE", "external_id": "UNAVAILABLE"})
        return [bad, good]

    async def fetch_book(self, market):
        if market.external_id == "UNAVAILABLE":
            raise httpx.ReadTimeout("Do not expose this response")
        return await super().fetch_book(market)


async def test_unrelated_book_failure_preserves_healthy_pair(database):
    settings, db, repository = database
    await Pipeline(
        settings, repository, [PartialFailureAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        rows = (await client.get("/api/v1/opportunities")).json()
        assert len(rows) == 1, "An unrelated failed market must not hide a fresh verified pair"
        status = (await client.get("/api/v1/status")).json()
        assert status["exchanges"][0]["status"] == "degraded"
        assert status["exchanges"][0]["fresh_book_count"] == 1
        feeds = {row["market_id"]: row for row in status["exchanges"][0]["market_health"]}
        assert feeds["kalshi:UNAVAILABLE"]["error"] == "ReadTimeout"
        assert feeds["kalshi:SIM-DEMO"]["status"] == "healthy"
        assert "Do not expose" not in str(status)


async def test_successful_http_response_with_old_book_is_not_healthy(database):
    class StaleAdapter(SimulationAdapter):
        async def fetch_book(self, market):
            book = await super().fetch_book(market)
            return book.model_copy(update={"source_at": utcnow() - timedelta(minutes=5)})

    settings, db, repository = database
    await Pipeline(
        settings, repository, [StaleAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        status = (await client.get("/api/v1/status")).json()
        assert not status["ingestion_healthy"], "HTTP success is not proof of current quotes"
        exchange = status["exchanges"][0]
        assert exchange["fresh_book_count"] == 0
        assert exchange["market_health"][0]["status"] == "stale"
        assert exchange["market_health"][0]["error"] == "book_stale"
        assert (await client.get("/api/v1/opportunities")).json() == []


async def test_quote_expiry_updates_health_without_another_ingestion_cycle(database, monkeypatch):
    settings, db, repository = database
    await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    later = utcnow() + timedelta(seconds=settings.max_quote_age_seconds + 1)
    monkeypatch.setattr("arbbot.storage.repository.utcnow", lambda: later)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        status = (await client.get("/api/v1/status")).json()
        assert not status["ingestion_healthy"]
        for exchange in status["exchanges"]:
            assert exchange["status"] == "degraded"  # Heartbeat is still within its 120s TTL.
            assert exchange["fresh_book_count"] == 0
            assert exchange["market_health"][0]["error"] == "book_stale"
        assert (await client.get("/api/v1/opportunities")).json() == []


async def test_failed_leg_is_hidden_before_publish_and_recovery_requires_reevaluation(database):
    settings, db, repository = database
    pipeline = Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    )
    await pipeline.cycle()

    class FailedLeg(SimulationAdapter):
        async def fetch_book(self, market):
            raise httpx.ReadTimeout("redacted")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        assert len((await client.get("/api/v1/opportunities")).json()) == 1
        await pipeline.ingest_venue(FailedLeg("kalshi"))
        # The old opportunity is still active in storage, but must not be served.
        async with db.sessions() as session:
            row = await session.scalar(select(OpportunityRecord))
            assert row.active
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 1
        await pipeline.ingest_venue(SimulationAdapter("kalshi"))
        assert (await client.get("/api/v1/status")).json()["ingestion_healthy"]
        assert (await client.get("/api/v1/opportunities")).json() == []
        await pipeline.cycle()
        assert len((await client.get("/api/v1/opportunities")).json()) == 1


async def test_discovery_failure_still_suppresses_the_venue(database):
    settings, db, repository = database
    pipeline = Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    )
    await pipeline.cycle()

    class FailedDiscovery(SimulationAdapter):
        async def discover(self, limit):
            raise httpx.ConnectError("redacted")

    await pipeline.ingest_venue(FailedDiscovery("kalshi"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        status = (await client.get("/api/v1/status")).json()
        assert not status["exchanges"][0]["discovery_ok"]
        assert (await client.get("/api/v1/opportunities")).json() == []


async def test_future_book_does_not_poison_latest_snapshot(database):
    settings, _, repository = database
    adapter = SimulationAdapter("kalshi")
    pipeline = Pipeline(settings, repository, [adapter, SimulationAdapter("polymarket")])
    await pipeline.cycle()
    original = await repository.book("simulation", "kalshi:SIM-DEMO")

    class FutureBook(SimulationAdapter):
        async def fetch_book(self, market):
            book = await super().fetch_book(market)
            return book.model_copy(update={"source_at": utcnow() + timedelta(days=1)})

    await pipeline.ingest_venue(FutureBook("kalshi"))
    assert (await repository.book("simulation", original.market_id)).id == original.id
    health = await repository.health("simulation", 120)
    assert health[0]["market_health"][0]["error"] == "book_from_future"
    assert not await repository.opportunities("simulation", 120)
    await pipeline.cycle()
    assert len(await repository.opportunities("simulation", 120)) == 1


async def test_ineligible_quotes_are_filtered_before_pagination(database):
    settings, db, repository = database
    await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    original = (await repository.opportunities("simulation", 120))[0]
    unavailable = original.model_copy(
        update={
            "id": "unavailable-opportunity",
            "net_profit": Decimal("100"),
            "legs": (
                original.legs[0].model_copy(update={"book_id": "unavailable-book"}),
                original.legs[1],
            ),
        }
    )
    matches = await repository.matches("simulation")
    await repository.publish(
        "simulation",
        matches,
        [
            Evaluation(
                match_id=original.match_id,
                mode="simulation",
                evaluated_at=original.evaluated_at,
                blocked_reasons=(),
                opportunities=(unavailable, original),
            )
        ],
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/opportunities?limit=1")
        assert response.status_code == 200
        assert [Opportunity.model_validate(row).id for row in response.json()] == [original.id]


async def test_unrelated_venue_health_does_not_hide_current_pair(database):
    settings, db, repository = database
    await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    await repository.set_health("simulation", "polymarket_us", "healthy", market_health=[])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        assert len((await client.get("/api/v1/opportunities")).json()) == 1
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 1


async def test_unrelated_discovery_failure_does_not_invalidate_pair(database):
    settings, _, repository = database
    await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    await repository.set_health("simulation", "polymarket_us", "degraded", error="offline")
    assert len(await repository.opportunities("simulation", 120)) == 1


async def test_us_pair_publication_and_disabled_international_history(database):
    # Synthetic publication contract only; this does not enable live US evaluation.
    from arbbot.domain import MarketHealth

    settings, db, repository = database
    await Pipeline(
        settings, repository, [SimulationAdapter("kalshi"), SimulationAdapter("polymarket")]
    ).cycle()
    original = (await repository.opportunities("simulation", 120))[0]
    us_adapter = SimulationAdapter("polymarket_us")
    market = (await us_adapter.discover(1))[0]
    book = await us_adapter.fetch_book(market)
    await repository.save_market(market)
    await repository.save_book(book)
    await repository.set_health(
        "simulation",
        "polymarket_us",
        "healthy",
        market_health=[
            MarketHealth(
                market_id=market.id,
                status="healthy",
                checked_at=utcnow(),
                book_id=book.id,
                quote_at=book.effective_at,
                valid_until=original.valid_until,
            )
        ],
    )
    opportunity = original.model_copy(
        update={
            "id": "synthetic-us-publication",
            "legs": (
                original.legs[0],
                original.legs[1].model_copy(
                    update={
                        "market_id": market.id,
                        "book_id": book.id,
                        "quote_at": book.effective_at,
                    }
                ),
            ),
        }
    )
    await repository.publish(
        "simulation",
        await repository.matches("simulation"),
        [
            Evaluation(
                match_id=original.match_id,
                mode="simulation",
                evaluated_at=utcnow(),
                blocked_reasons=(),
                opportunities=(opportunity, original),
            )
        ],
    )
    settings = settings.model_copy(update={"enabled_venues": ("kalshi", "polymarket_us")})
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        rows = (await client.get("/api/v1/opportunities")).json()
        assert [row["id"] for row in rows] == [opportunity.id]
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 2
        await repository.set_health("simulation", "polymarket_us", "degraded", error="offline")
        assert (await client.get("/api/v1/opportunities")).json() == []
        assert len((await client.get("/api/v1/opportunities/history")).json()) == 2
