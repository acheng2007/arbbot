from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from arbbot.domain import Book, Market, MarketHealth, Match, Opportunity, digest, restore, utcnow
from arbbot.storage.models import (
    EvaluationRecord,
    HealthRecord,
    MarketRecord,
    MarketVersionRecord,
    MatchRecord,
    OpportunityRecord,
    SnapshotRecord,
)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class Repository:
    def __init__(self, database):
        self.database = database

    async def save_market(self, market: Market):
        async with self.database.sessions.begin() as session:
            key = f"{market.mode}:{market.id}"
            row = await session.get(MarketRecord, key)
            if row and aware(row.observed_at) > market.observed_at:
                return
            if row is None:
                row = MarketRecord(key=key, id=market.id, mode=market.mode, venue=market.venue)
                session.add(row)
            row.payload = market.model_dump(mode="json")
            row.observed_at = market.observed_at
            await session.flush()
            version_id = digest([market.mode, market.id, market.terms_hash])
            if not await session.get(MarketVersionRecord, version_id):
                session.add(
                    MarketVersionRecord(
                        id=version_id,
                        market_key=key,
                        terms_hash=market.terms_hash,
                        payload=market.model_dump(mode="json"),
                    )
                )

    async def market_version(self, mode, market_id, terms_hash):
        async with self.database.sessions() as session:
            row = await session.get(MarketVersionRecord, digest([mode, market_id, terms_hash]))
            return restore(Market, row.payload) if row else None

    async def snapshot(self, mode, snapshot_id):
        async with self.database.sessions() as session:
            row = await session.scalar(
                select(SnapshotRecord)
                .join(MarketRecord, MarketRecord.key == SnapshotRecord.market_key)
                .where(SnapshotRecord.id == snapshot_id, MarketRecord.mode == mode)
            )
            return Book.model_validate(row.payload) if row else None

    async def save_book(self, book: Book) -> bool:
        async with self.database.sessions.begin() as session:
            row = await session.get(
                MarketRecord, f"{book.mode}:{book.market_id}", with_for_update=True
            )
            if row is None:
                raise ValueError("Market must be persisted before its order book")
            if row.latest_book_id:
                previous = await session.get(SnapshotRecord, row.latest_book_id)
                old = Book.model_validate(previous.payload)
                if book.received_at < old.received_at or (
                    book.source_at and old.source_at and book.source_at < old.source_at
                ):
                    return False
            if not await session.get(SnapshotRecord, book.id):
                session.add(
                    SnapshotRecord(
                        id=book.id,
                        market_key=row.key,
                        received_at=book.received_at,
                        payload=book.model_dump(mode="json"),
                    )
                )
            row.latest_book_id = book.id
            return True

    async def markets(self, mode, *, limit=100, offset=0, venue=None):
        query = select(MarketRecord).where(MarketRecord.mode == mode)
        if venue:
            query = query.where(MarketRecord.venue == venue)
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(query.order_by(MarketRecord.id).limit(limit).offset(offset))
            ).all()
            return [restore(Market, row.payload) for row in rows]

    async def market(self, mode, market_id):
        async with self.database.sessions() as session:
            row = await session.get(MarketRecord, f"{mode}:{market_id}")
            return restore(Market, row.payload) if row else None

    async def book(self, mode, market_id):
        async with self.database.sessions() as session:
            row = await session.get(MarketRecord, f"{mode}:{market_id}")
            if not row or not row.latest_book_id:
                return None
            snapshot = await session.get(SnapshotRecord, row.latest_book_id)
            return Book.model_validate(snapshot.payload)

    async def health(self, mode, health_max_age: int):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(select(HealthRecord).where(HealthRecord.mode == mode))
            ).all()
        results = []
        now = utcnow()
        for row in rows:
            heartbeat_stale = now - aware(row.checked_at) > timedelta(seconds=health_max_age)
            feeds = []
            for payload in row.payload.get("market_health", []):
                feed = MarketHealth.model_validate(payload)
                if feed.status == "healthy":
                    if heartbeat_stale:
                        feed = feed.model_copy(update={"status": "stale", "error": "worker_stale"})
                    elif feed.valid_until is None or not feed.book_id:
                        feed = feed.model_copy(update={"status": "error", "error": "book_missing"})
                    elif now >= feed.valid_until:
                        feed = feed.model_copy(update={"status": "stale", "error": "book_stale"})
                feeds.append(feed)
            status = row.status
            errors = {feed.error for feed in feeds if feed.error}
            if row.payload.get("error"):
                errors.update(row.payload["error"].split(","))
            if not row.payload.get("discovery_ok", False):
                status = "degraded"
            elif any(feed.status in {"stale", "error"} for feed in feeds):
                status = "degraded"
            results.append(
                {
                    **row.payload,
                    "status": "stale" if heartbeat_stale else status,
                    "fresh_book_count": sum(feed.status == "healthy" for feed in feeds),
                    "market_health": [feed.model_dump(mode="json") for feed in feeds],
                    "error": ",".join(sorted(errors)) if errors else None,
                }
            )
        return sorted(results, key=lambda row: row["venue"])

    async def set_health(
        self,
        mode,
        venue,
        status,
        market_count=0,
        book_count=0,
        error=None,
        *,
        market_health: list[MarketHealth] | None = None,
    ):
        now = utcnow()
        async with self.database.sessions.begin() as session:
            await session.merge(
                HealthRecord(
                    key=f"{mode}:{venue}",
                    mode=mode,
                    venue=venue,
                    status=status,
                    checked_at=now,
                    payload={
                        "venue": venue,
                        "mode": mode,
                        "status": status,
                        "checked_at": now.isoformat(),
                        "market_count": market_count,
                        "book_count": book_count,
                        "error": error,
                        "discovery_ok": market_health is not None,
                        "market_health": [
                            feed.model_dump(mode="json") for feed in market_health or []
                        ],
                    },
                )
            )
            # Without a complete catalog, no pair using this venue is trustworthy.
            # Partial book failures are filtered per leg by opportunities() instead.
            if market_health is None:
                await session.execute(
                    update(OpportunityRecord)
                    .where(OpportunityRecord.mode == mode)
                    .values(active=False)
                )

    async def publish(self, mode, matches, evaluations):
        # Publish a coherent cycle in one transaction; retain past calculations for audit.
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(MatchRecord).where(MatchRecord.mode == mode).values(current=False)
            )
            await session.execute(
                update(OpportunityRecord).where(OpportunityRecord.mode == mode).values(active=False)
            )
            for match in matches:
                await session.merge(
                    MatchRecord(
                        id=match.id, mode=mode, current=True, payload=match.model_dump(mode="json")
                    )
                )
            await session.flush()
            for result in evaluations:
                session.add(
                    EvaluationRecord(
                        id=str(uuid4()),
                        match_id=result.match_id,
                        mode=mode,
                        evaluated_at=result.evaluated_at,
                        payload=result.model_dump(mode="json"),
                    )
                )
                for opportunity in result.opportunities:
                    await session.merge(
                        OpportunityRecord(
                            id=opportunity.id,
                            match_id=opportunity.match_id,
                            mode=mode,
                            active=True,
                            evaluated_at=opportunity.evaluated_at,
                            valid_until=opportunity.valid_until,
                            net_profit=opportunity.net_profit,
                            capital_required=opportunity.capital_required,
                            payload=opportunity.model_dump(mode="json"),
                        )
                    )

    async def matches(self, mode, limit=100, offset=0):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(MatchRecord)
                    .where(MatchRecord.mode == mode, MatchRecord.current.is_(True))
                    .order_by(MatchRecord.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [Match.model_validate(row.payload) for row in rows]

    async def opportunities(self, mode, health_max_age, limit=100, offset=0, history=False):
        eligible_books = []
        if not history:
            health = await self.health(mode, health_max_age)
            available = [h for h in health if h["status"] != "stale" and h.get("discovery_ok")]
            if {h["venue"] for h in available} != {"kalshi", "polymarket"}:
                return []
            eligible_books = [
                feed["book_id"]
                for venue in available
                for feed in venue["market_health"]
                if feed["status"] == "healthy" and feed["book_id"]
            ]
        query = select(OpportunityRecord).where(OpportunityRecord.mode == mode)
        if not history:
            query = query.where(
                OpportunityRecord.active.is_(True), OpportunityRecord.valid_until > utcnow()
            )
            # Apply eligibility before pagination and sorting. Matching exact snapshots
            # also prevents replaying a previous opportunity after a failed market recovers.
            for leg in (0, 1):
                query = query.where(
                    OpportunityRecord.payload["legs"][leg]["book_id"]
                    .as_string()
                    .in_(eligible_books)
                )
        query = (
            query.order_by(
                OpportunityRecord.evaluated_at.desc(),
                OpportunityRecord.net_profit.desc(),
                OpportunityRecord.id,
            )
            .limit(limit)
            .offset(offset)
        )
        async with self.database.sessions() as session:
            return [
                Opportunity.model_validate(row.payload)
                for row in (await session.scalars(query)).all()
            ]

    async def evaluations(self, mode, limit=100, offset=0):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(EvaluationRecord)
                    .where(EvaluationRecord.mode == mode)
                    .order_by(EvaluationRecord.evaluated_at.desc(), EvaluationRecord.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [row.payload for row in rows]
