from sqlalchemy import or_, select

from arbbot.domain import Market, Match, restore
from arbbot.storage.models import MarketRecord, MatchRecord


def market_predicates(mode, *, venue=None, status=None, family=None, q=None):
    predicates = [MarketRecord.mode == mode]
    if venue is not None:
        predicates.append(MarketRecord.venue == venue)
    if status is not None:
        predicates.append(MarketRecord.payload["status"].as_string() == status)
    if family is not None:
        predicates.append(MarketRecord.family == family)
    if q is not None:
        # Escape SQL LIKE wildcards; text is a literal, parameterized substring.
        escaped = q.replace("/", "//").replace("%", "/%").replace("_", "/_")
        pattern = "%" + escaped + "%"
        predicates.append(
            or_(
                MarketRecord.id.ilike(pattern, escape="/"),
                MarketRecord.payload["title"].as_string().ilike(pattern, escape="/"),
                MarketRecord.payload["rules"].as_string().ilike(pattern, escape="/"),
            )
        )
    return predicates


class CatalogQueries:
    def __init__(self, database):
        self.database = database

    async def markets(self, mode, *, limit=100, offset=0, **filters):
        query = select(MarketRecord).where(*market_predicates(mode, **filters))
        async with self.database.sessions() as session:
            rows = await session.scalars(
                query.order_by(MarketRecord.id).limit(limit).offset(offset)
            )
            return [restore(Market, row.payload) for row in rows]

    async def matches(
        self,
        mode,
        *,
        limit=100,
        offset=0,
        status=None,
        evidence=None,
        venue=None,
        family=None,
        q=None,
    ):
        query = select(MatchRecord).where(MatchRecord.mode == mode, MatchRecord.current.is_(True))
        if status is not None:
            query = query.where(MatchRecord.payload["status"].as_string() == status)
        if evidence is not None:
            query = query.where(MatchRecord.evidence_complete.is_(evidence == "complete"))
        if any(value is not None for value in (venue, family, q)):
            # All market-side filters must match the same leg. EXISTS avoids duplicated pairs.
            matching_leg = (
                select(MarketRecord.key)
                .where(
                    *market_predicates(mode, venue=venue, family=family, q=q),
                    or_(
                        MarketRecord.id == MatchRecord.payload["left_id"].as_string(),
                        MarketRecord.id == MatchRecord.payload["right_id"].as_string(),
                    ),
                )
                .exists()
            )
            query = query.where(matching_leg)
        async with self.database.sessions() as session:
            rows = await session.scalars(query.order_by(MatchRecord.id).limit(limit).offset(offset))
            return [Match.model_validate(row.payload) for row in rows]
