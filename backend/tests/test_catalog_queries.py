from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, text, update

from arbbot.api.app import create_app
from arbbot.domain import utcnow
from arbbot.matching.contracts import compare_contracts
from arbbot.storage.models import MarketRecord, MatchRecord
from tests.test_contracts import definition


@pytest.fixture
async def catalog_data(database, fixture_market):
    settings, db, repository = database
    originals, _, _, base_match = fixture_market
    markets = []
    for i in range(6):
        original = originals[i % 2]
        market = original.model_copy(
            update={
                "id": f"{original.venue}:catalog-{i}",
                "external_id": f"catalog-{i}",
                "title": f"US CPI for August 2026 item {i}",
                "rules": "US CPI for August 2026. Literal 50%_test / evidence.",
                "status": "closed" if i == 4 else "open",
            }
        )
        markets.append(market)
        await repository.save_market(market)
        await repository.save_market(market.model_copy(update={"mode": "live", "title": "secret"}))
    matches = []
    for i, status in enumerate(("candidate", "verified", "rejected")):
        left, right = markets[2 * i : 2 * i + 2]
        comparison = (
            compare_contracts(left, right, definition(left), definition(right)) if i else None
        )
        matches.append(
            base_match.model_copy(
                update={
                    "id": f"pair-{i}",
                    "left_id": left.id,
                    "right_id": right.id,
                    "status": status,
                    "comparison": comparison,
                }
            )
        )
    await repository.publish(settings.mode, matches, [])
    await repository.publish(
        "live", [m.model_copy(update={"id": "live-" + m.id, "mode": "live"}) for m in matches], []
    )
    return settings, db, repository, markets, matches


async def test_combined_filters_before_stable_pagination(catalog_data):
    settings, db, _, markets, _ = catalog_data
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        params = {
            "venue": "kalshi",
            "status": "open",
            "family": "cpi",
            "q": "cPi",
            "limit": 1,
            "offset": 1,
        }
        response = await client.get("/api/v1/markets", params=params)
        assert response.status_code == 200
        assert [m["id"] for m in response.json()] == [markets[2].id]
        assert (await client.get("/api/v1/markets", params=params)).json() == response.json()
        assert (await client.get("/api/v1/markets", params={"q": "secret"})).json() == []
        assert (await client.get("/api/v1/markets", params={"family": "unknown"})).json() == []
        assert len((await client.get("/api/v1/markets")).json()) == 6


@pytest.mark.parametrize(
    "query,count", [("50%_test", 6), ("%_missing", 0), ("' OR 1=1 --", 0), ("/ evidence", 6)]
)
async def test_search_is_literal_and_parameterized(catalog_data, query, count):
    settings, db, *_ = catalog_data
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        assert len((await client.get("/api/v1/markets", params={"q": query})).json()) == count


async def test_match_status_completeness_and_same_leg_filters(catalog_data):
    settings, db, repository, markets, _ = catalog_data
    # Label only the Polymarket leg with the search term.
    await repository.save_market(markets[3].model_copy(update={"title": "unique token"}))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/matches",
            params={
                "status": "verified",
                "evidence": "complete",
                "family": "cpi",
                "limit": 1,
            },
        )
        assert [m["id"] for m in response.json()] == ["pair-1"]
        assert (
            len((await client.get("/api/v1/matches", params={"evidence": "incomplete"})).json())
            == 1
        )
        assert (
            await client.get("/api/v1/matches", params={"venue": "kalshi", "q": "unique token"})
        ).json() == []
        assert (
            len(
                (
                    await client.get(
                        "/api/v1/matches", params={"venue": "polymarket", "q": "unique token"}
                    )
                ).json()
            )
            == 1
        )
        async with db.sessions.begin() as session:
            await session.execute(
                update(MatchRecord).where(MatchRecord.id == "pair-1").values(current=False)
            )
        assert (await client.get("/api/v1/matches", params={"status": "verified"})).json() == []


async def test_family_refreshes_with_terms_but_not_older_updates(catalog_data):
    _, db, repository, markets, _ = catalog_data
    market = markets[0]
    newer = market.model_copy(
        update={
            "title": "Unknown event",
            "rules": "Unknown rules",
            "observed_at": utcnow() + timedelta(seconds=1),
        }
    )
    await repository.save_market(newer)
    await repository.save_market(market)
    async with db.sessions() as session:
        row = await session.get(MarketRecord, f"simulation:{market.id}")
        assert row.family is None


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 201},
        {"offset": -1},
        {"offset": 100001},
        {"venue": "bad"},
        {"q": "x" * 201},
        {"family": "x" * 101},
    ],
)
async def test_api_bounds(catalog_data, params):
    settings, db, *_ = catalog_data
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, db)), base_url="http://test"
    ) as client:
        for path in ("markets", "matches"):
            assert (await client.get("/api/v1/" + path, params=params)).status_code == 422


async def test_family_index_supports_ordered_mode_scoped_query(catalog_data):
    _, db, *_ = catalog_data
    query = (
        select(MarketRecord.id)
        .where(MarketRecord.mode == "simulation", MarketRecord.family == "cpi")
        .order_by(MarketRecord.id)
        .limit(1)
    )
    compiled = str(query.compile(db.engine.sync_engine, compile_kwargs={"literal_binds": True}))
    async with db.sessions.begin() as session:
        if db.engine.dialect.name == "postgresql":
            # Small fixtures favor scans; check index eligibility, not production latency.
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            plan = await session.execute(text("EXPLAIN " + compiled))
        else:
            plan = await session.execute(text("EXPLAIN QUERY PLAN " + compiled))
        assert "ix_market_family_page" in str(plan.all())
