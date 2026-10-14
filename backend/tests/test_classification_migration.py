"""Additive classification migration preserves existing matching and source payloads."""

from sqlalchemy import select

from arbbot.domain import Match
from arbbot.storage.models import Base, ClassificationJobRecord, MarketRecord, MatchRecord
from tests.test_catalog_migration import migrate


async def test_additive_migration_preserves_legacy_matches(database, fixture_market):
    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "b023_evaluation_heads")
    markets, _, _, match = fixture_market
    for market in markets:
        await repository.save_market(market)
    payload = match.model_dump(mode="json", exclude={"classification", "ai_only"})
    async with db.sessions.begin() as session:
        session.add(
            MatchRecord(
                id=match.id, mode=match.mode, current=True, evidence_complete=False, payload=payload
            )
        )
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    async with db.sessions() as session:
        row = await session.get(MatchRecord, match.id)
        assert row.payload == payload
        assert Match.model_validate(row.payload).classification is None
        assert (await session.get(MarketRecord, "simulation:" + markets[0].id)).payload[
            "rules"
        ] == markets[0].rules
        assert not (await session.scalars(select(ClassificationJobRecord))).all()
    await migrate(settings, "downgrade", "b023_evaluation_heads")
    await migrate(settings, "upgrade", "head")
    async with db.sessions() as session:
        assert (await session.get(MatchRecord, match.id)).payload == payload
