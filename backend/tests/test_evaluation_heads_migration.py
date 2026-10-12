"""Latest heads and unscaled NUMERIC preserve historical payloads and exact money."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import insert, select

from arbbot.arbitrage.engine import evaluate
from arbbot.domain import utcnow
from arbbot.storage.models import (
    Base,
    EvaluationHeadRecord,
    EvaluationRecord,
    MatchRecord,
    OpportunityRecord,
)
from tests.test_catalog_migration import migrate


async def test_upgrade_backfills_latest_heads_and_preserves_exact_payloads(
    database, fixture_market
):
    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "b022_execution_configuration")
    markets, books, _, match = fixture_market
    for market in markets:
        await repository.save_market(market)
        await repository.save_book(books[market.id])
    result = evaluate(match, *markets, books, settings, utcnow())
    precise = Decimal("1.234567891234567891234567891")
    opportunity = result.opportunities[0].model_copy(update={"net_profit": precise})
    result = result.model_copy(
        update={
            "opportunities": (opportunity,),
            "best_calculation": result.best_calculation.model_copy(update={"net_profit": precise}),
        }
    )
    async with db.sessions.begin() as session:
        await session.execute(
            insert(MatchRecord).values(
                id=match.id,
                mode=match.mode,
                current=True,
                evidence_complete=False,
                payload=match.model_dump(mode="json"),
            )
        )
        for identifier, instant in (
            ("older", result.evaluated_at - timedelta(seconds=1)),
            ("newer", result.evaluated_at),
        ):
            await session.execute(
                insert(EvaluationRecord).values(
                    id=identifier,
                    match_id=match.id,
                    mode=match.mode,
                    evaluated_at=instant,
                    payload=result.model_dump(mode="json"),
                )
            )
        await session.execute(
            insert(OpportunityRecord).values(
                id=opportunity.id,
                match_id=match.id,
                mode=match.mode,
                active=True,
                evaluated_at=result.evaluated_at,
                valid_until=opportunity.valid_until,
                net_profit=precise,
                capital_required=opportunity.capital_required,
                payload=opportunity.model_dump(mode="json"),
            )
        )
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    async with db.sessions() as session:
        head = await session.get(EvaluationHeadRecord, match.id)
        assert head.evaluation_id == "newer"
        row = await session.get(OpportunityRecord, opportunity.id)
        assert row.payload["net_profit"] == str(precise)
        if db.engine.dialect.name == "postgresql":
            assert row.net_profit == precise
            assert (await session.get(EvaluationRecord, "newer")).net_profit == precise
    assert len(await repository.evaluations("simulation")) == 1
    assert len(await repository.evaluations("simulation", history=True)) == 2
    await migrate(settings, "downgrade", "b022_execution_configuration")
    await migrate(settings, "upgrade", "head")
    async with db.sessions() as session:
        assert await session.scalar(select(EvaluationHeadRecord.evaluation_id)) == "newer"
