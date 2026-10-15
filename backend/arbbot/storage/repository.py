from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import case, false, or_, select, update

from arbbot.domain import Book, Market, MarketHealth, Opportunity, digest, restore, utcnow
from arbbot.matching.extraction import extract_contract
from arbbot.storage.models import (
    EvaluationHeadRecord,
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
    def __init__(self, database, *, allow_file_reviews=False):
        self.database = database
        self.allow_file_reviews = allow_file_reviews

    async def save_market(self, market: Market, *, from_catalog=False):
        async with self.database.sessions.begin() as session:
            await self.save_market_in_session(session, market, from_catalog=from_catalog)

    async def save_market_in_session(self, session, market: Market, *, from_catalog=False):
        key = f"{market.mode}:{market.id}"
        row = await session.get(MarketRecord, key, with_for_update=True)
        if row and aware(row.observed_at) > market.observed_at:
            return
        if row is None:
            row = MarketRecord(key=key, id=market.id, mode=market.mode, venue=market.venue)
            session.add(row)
        previous = row.payload or {}
        market = market.model_copy(
            update={
                "source_revision": previous.get("source_revision", 0),
                "ingestion_issues": market.ingestion_issues
                if from_catalog
                else tuple(previous.get("ingestion_issues", market.ingestion_issues)),
            }
        )
        row.payload = market.model_dump(mode="json")
        row.observed_at = market.observed_at
        metric = extract_contract(market).definition.facts.get("metric")
        row.family = metric.value if metric and metric.value != "unknown" else None
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

    async def latest_books(self, mode):
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(SnapshotRecord)
                    .join(MarketRecord, MarketRecord.latest_book_id == SnapshotRecord.id)
                    .where(MarketRecord.mode == mode)
                )
            ).all()
        return {row.payload["market_id"]: Book.model_validate(row.payload) for row in rows}

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
            if market_health is not None:
                previous = await session.get(HealthRecord, f"{mode}:{venue}", with_for_update=True)
                incoming = {feed.market_id: feed for feed in market_health}
                if previous:
                    for payload in previous.payload.get("market_health", []):
                        feed = MarketHealth.model_validate(payload)
                        if feed.market_id not in incoming and (
                            feed.valid_until > now
                            if feed.valid_until
                            else feed.checked_at > now - timedelta(seconds=120)
                        ):
                            incoming[feed.market_id] = feed
                market_health = list(incoming.values())
                book_count = sum(feed.status == "healthy" for feed in market_health)
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
            # Without a current catalog, pairs using this venue are not trustworthy.
            # Partial book failures are filtered per leg by opportunities() instead.
            if market_health is None:
                await session.execute(
                    update(OpportunityRecord)
                    .where(
                        OpportunityRecord.mode == mode,
                        or_(
                            *(
                                OpportunityRecord.payload["legs"][leg]["market_id"]
                                .as_string()
                                .startswith(venue + ":")
                                for leg in (0, 1)
                            )
                        ),
                    )
                    .values(active=False)
                )

    async def publish(
        self,
        mode,
        matches,
        evaluations,
        *,
        replace_generation=True,
        settings=None,
        write_matches=True,
    ):
        from arbbot.reviews.provider import guard_publication

        # Publish a coherent cycle in one transaction; retain past calculations for audit.
        async with self.database.sessions.begin() as session:
            matches, evaluations = await guard_publication(
                self.database, session, mode, matches, evaluations
            )
            if settings is not None:
                from arbbot.execution.publication import guard_execution

                evaluations = await guard_execution(
                    self.database,
                    session,
                    mode,
                    evaluations,
                    settings,
                    require_current_match=not write_matches,
                )
            if replace_generation:
                await session.execute(
                    update(MatchRecord).where(MatchRecord.mode == mode).values(current=False)
                )
                retained = [match.id for match in matches]
                await session.execute(
                    update(OpportunityRecord)
                    .where(
                        OpportunityRecord.mode == mode,
                        OpportunityRecord.match_id.not_in(retained),
                    )
                    .values(active=False)
                )
            evaluated_ids = [result.match_id for result in evaluations]
            await session.execute(
                update(OpportunityRecord)
                .where(
                    OpportunityRecord.mode == mode,
                    OpportunityRecord.match_id.in_(evaluated_ids),
                )
                .values(active=False)
            )
            for match in matches if write_matches else ():
                await session.merge(
                    MatchRecord(
                        id=match.id,
                        mode=mode,
                        current=True,
                        payload=match.model_dump(mode="json"),
                        evidence_complete=bool(
                            match.comparison
                            and match.comparison.left
                            and match.comparison.right
                            and not match.comparison.issues
                            and match.comparison.differences
                            and all(d.status != "unknown" for d in match.comparison.differences)
                        ),
                    )
                )
            await session.flush()
            for result in evaluations:
                evaluation_id = str(uuid4())
                session.add(
                    EvaluationRecord(
                        id=evaluation_id,
                        match_id=result.match_id,
                        status=result.status,
                        net_profit=result.best_calculation.net_profit
                        if result.best_calculation
                        else None,
                        capital_required=result.best_calculation.capital_required
                        if result.best_calculation
                        else None,
                        mode=mode,
                        evaluated_at=result.evaluated_at,
                        payload=result.model_dump(mode="json"),
                    )
                )
                await session.flush()
                await session.merge(
                    EvaluationHeadRecord(
                        match_id=result.match_id, mode=mode, evaluation_id=evaluation_id
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
        return sum(len(result.opportunities) for result in evaluations)

    async def matches(self, mode, limit=100, offset=0):
        from arbbot.storage.catalog_queries import CatalogQueries

        return await CatalogQueries(
            self.database, allow_file_reviews=self.allow_file_reviews
        ).matches(mode, limit=limit, offset=offset)

    async def opportunities(
        self,
        mode,
        health_max_age,
        limit=100,
        offset=0,
        history=False,
        enabled_venues=None,
        opportunity_id=None,
    ):
        eligible_books = []
        if not history:
            health = await self.health(mode, health_max_age)
            available = [
                h
                for h in health
                if h["status"] != "stale"
                and h.get("discovery_ok")
                and (enabled_venues is None or h["venue"] in enabled_venues)
            ]
            eligible_books = [
                feed["book_id"]
                for venue in available
                for feed in venue["market_health"]
                if feed["status"] == "healthy" and feed["book_id"]
            ]
        query = select(OpportunityRecord).where(OpportunityRecord.mode == mode)
        if opportunity_id is not None:
            query = query.where(OpportunityRecord.id == opportunity_id)
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
                query = query.where(
                    select(MarketRecord.key)
                    .where(
                        MarketRecord.mode == mode,
                        MarketRecord.id
                        == OpportunityRecord.payload["legs"][leg]["market_id"].as_string(),
                        MarketRecord.latest_book_id
                        == OpportunityRecord.payload["legs"][leg]["book_id"].as_string(),
                    )
                    .exists()
                )
        ordering = (
            OpportunityRecord.evaluated_at.desc(),
            OpportunityRecord.net_profit.desc(),
            OpportunityRecord.id,
        )
        if not history:
            from arbbot.reviews.repository import ReviewRepository

            reviews = ReviewRepository(self.database)
            async with reviews._read() as session:
                revision = OpportunityRecord.payload["review_revision_id"].as_string()
                left_id = OpportunityRecord.payload["review"]["left_id"].as_string()
                right_id = OpportunityRecord.payload["review"]["right_id"].as_string()
                pairs = (
                    await session.execute(
                        query.with_only_columns(revision, left_id, right_id)
                        .where(revision.is_not(None))
                        .distinct()
                    )
                ).all()
                eligible = []
                for revision_id, left, right in pairs:
                    state = await reviews.decision_in_session(session, mode, left, right)
                    if state and state.eligible and state.revision.id == revision_id:
                        eligible.append(revision_id)
                legacy = (
                    revision.is_(None)
                    if mode == "simulation" or self.allow_file_reviews
                    else false()
                )
                automatic = OpportunityRecord.payload["qualification"]["assessment_id"].as_string()
                query = query.where(or_(legacy, revision.in_(eligible), automatic.is_not(None)))
                from arbbot.execution.repository import ExecutionRepository

                configuration = ExecutionRepository(self.database)
                rows = (await session.scalars(query.order_by(*ordering))).all()
                current = []
                for row in rows:
                    opportunity = Opportunity.model_validate(row.payload)
                    from arbbot.qualification.providers import requires_context
                    from arbbot.qualification.service import current as qualification_current

                    automatic = opportunity.qualification is not None
                    if automatic:
                        summary, _ = await qualification_current(
                            session, mode, opportunity.match_id
                        )
                        if summary.status != "qualified" or (
                            summary.assessment_id != opportunity.qualification.assessment_id
                        ):
                            continue
                    markets = []
                    for leg in opportunity.legs:
                        market_row = await session.get(MarketRecord, f"{mode}:{leg.market_id}")
                        if market_row:
                            markets.append(restore(Market, market_row.payload))
                    if mode == "live" and (automatic or requires_context(markets)):
                        if len(markets) != 2:
                            continue
                        context = await (
                            configuration.public_context(session, mode, markets)
                            if automatic
                            else configuration.context(session, mode, markets)
                        )
                        if context.blocked_reasons or (
                            opportunity.access_revision_id != context.access_revision_id
                            or opportunity.applicability_revision_ids
                            != context.applicability_revision_ids
                            or opportunity.fee_revision_ids != context.fee_revision_ids
                        ):
                            continue
                    current.append(opportunity)
                return current[offset : offset + limit]
        query = (
            query.order_by(
                *ordering,
            )
            .limit(limit)
            .offset(offset)
        )
        async with self.database.sessions() as session:
            return [
                Opportunity.model_validate(row.payload)
                for row in (await session.scalars(query)).all()
            ]

    async def evaluations(
        self, mode, limit=100, offset=0, *, history=False, match_id=None, status=None
    ):
        from arbbot.domain import Evaluation

        query = select(EvaluationRecord).where(EvaluationRecord.mode == mode)
        if match_id is not None:
            query = query.where(EvaluationRecord.match_id == match_id)
        if not history:
            query = query.join(
                EvaluationHeadRecord, EvaluationHeadRecord.evaluation_id == EvaluationRecord.id
            )
        if not history:
            reviewed = (
                select(MatchRecord.payload["status"].as_string())
                .where(MatchRecord.id == EvaluationRecord.match_id)
                .scalar_subquery()
            )
            query = query.order_by(case((reviewed == "verified", 0), else_=1))
        query = query.order_by(EvaluationRecord.evaluated_at.desc(), EvaluationRecord.id)
        if status is None:
            query = query.limit(limit).offset(offset)
        async with self.database.sessions() as session:
            rows = (await session.scalars(query)).all()
        values = [Evaluation.model_validate(row.payload) for row in rows]
        if status is not None:
            values = [value for value in values if value.status == status]
        return values[offset : offset + limit] if status is not None else values
