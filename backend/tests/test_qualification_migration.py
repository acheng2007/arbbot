"""The additive automatic assessment tables preserve legacy review payloads."""

from sqlalchemy import select

from arbbot.domain import Match
from arbbot.storage.models import Base, MatchRecord, QualificationRunRecord
from tests.test_catalog_migration import migrate


async def test_automatic_migration_preserves_historical_payloads(database, fixture_market):
    settings, db, repository = database
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await migrate(settings, "upgrade", "b024_classification")
    markets, _, _, match = fixture_market
    for market in markets:
        await repository.save_market(market)
    original = match.model_dump(mode="json", exclude={"qualification", "settlement"})
    async with db.sessions.begin() as session:
        session.add(
            MatchRecord(
                id=match.id,
                mode=match.mode,
                current=True,
                evidence_complete=False,
                payload=original,
            )
        )
    await migrate(settings, "upgrade", "head")
    await migrate(settings, "check")
    async with db.sessions() as session:
        row = await session.get(MatchRecord, match.id)
        assert row.payload == original
        assert Match.model_validate(row.payload).qualification is None
        assert not (await session.scalars(select(QualificationRunRecord))).all()
    await migrate(settings, "downgrade", "b024_classification")
    await migrate(settings, "upgrade", "head")
    async with db.sessions() as session:
        assert (await session.get(MatchRecord, match.id)).payload == original
