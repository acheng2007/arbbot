from sqlalchemy import or_, select

from arbbot.domain import Market, MarketSummary, Match, restore
from arbbot.storage.models import MarketRecord, MatchRecord


def market_predicates(
    mode, *, venue=None, status=None, family=None, q=None, venues=None, category=None
):
    predicates = [MarketRecord.mode == mode]
    if venues is not None:
        predicates.append(MarketRecord.venue.in_(venues))
    if venue is not None:
        predicates.append(MarketRecord.venue == venue)
    if status is not None:
        predicates.append(MarketRecord.payload["status"].as_string() == status)
    if category is not None:
        predicates.append(MarketRecord.payload["category"].as_string() == category)
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
    def __init__(self, database, *, allow_file_reviews=False, venues=None):
        self.database = database
        self.venues = venues
        self.allow_file_reviews = allow_file_reviews

    async def markets(self, mode, *, limit=100, offset=0, **filters):
        query = select(MarketRecord).where(*market_predicates(mode, venues=self.venues, **filters))
        async with self.database.sessions() as session:
            rows = await session.scalars(
                query.order_by(MarketRecord.id).limit(limit).offset(offset)
            )
            return [restore(Market, row.payload) for row in rows]

    async def summaries(self, mode, *, limit=100, offset=0, **filters):
        fields = list(MarketSummary.model_fields)
        query = select(*(MarketRecord.payload[field].as_string().label(field) for field in fields))
        query = query.where(*market_predicates(mode, venues=self.venues, **filters))
        async with self.database.sessions() as session:
            rows = (
                (await session.execute(query.order_by(MarketRecord.id).limit(limit).offset(offset)))
                .mappings()
                .all()
            )
        return [MarketSummary.model_validate(dict(row)) for row in rows]

    async def matches(
        self,
        mode,
        *,
        limit=100,
        offset=0,
        status=None,
        evidence=None,
        market_id=None,
        match_id=None,
        venue=None,
        family=None,
        q=None,
    ):
        query = select(MatchRecord).where(MatchRecord.mode == mode, MatchRecord.current.is_(True))
        if market_id is not None:
            query = query.where(
                or_(
                    MatchRecord.payload["left_id"].as_string() == market_id,
                    MatchRecord.payload["right_id"].as_string() == market_id,
                )
            )
        if match_id is not None:
            query = query.where(MatchRecord.id == match_id)
        if self.venues is not None:
            for side in ("left_id", "right_id"):
                query = query.where(
                    select(MarketRecord.key)
                    .where(
                        MarketRecord.mode == mode,
                        MarketRecord.venue.in_(self.venues),
                        MarketRecord.id == MatchRecord.payload[side].as_string(),
                    )
                    .exists()
                )
        if status is not None:
            query = query.where(MatchRecord.payload["status"].as_string().in_({status, "verified"}))
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
        from arbbot.reviews.provider import refresh_match
        from arbbot.reviews.repository import ReviewRepository

        reviews = ReviewRepository(self.database)
        results, skipped, cursor = [], 0, None
        async with reviews._read() as session:
            # Revalidate before filtering/pagination. Keyset batches bound memory
            # even when a requested page follows many invalidated approvals.
            while len(results) < limit:
                page = query.where(MatchRecord.id > cursor) if cursor else query
                rows = (await session.scalars(page.order_by(MatchRecord.id).limit(200))).all()
                if not rows:
                    break
                for row in rows:
                    match = await refresh_match(
                        reviews,
                        session,
                        mode,
                        Match.model_validate(row.payload),
                        allow_file_reviews=self.allow_file_reviews,
                    )
                    if status is not None and match.status != status:
                        continue
                    if skipped < offset:
                        skipped += 1
                    else:
                        results.append(match)
                        if len(results) == limit:
                            break
                cursor = rows[-1].id
        return results
