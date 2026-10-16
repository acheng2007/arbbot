from sqlalchemy import and_, case, func, or_, select

from arbbot.domain import Market, MarketSummary, Match, restore
from arbbot.storage.models import MarketRecord, MatchRecord


def category_expression():
    from arbbot.discovery.categories import ALIASES

    raw = func.lower(func.coalesce(MarketRecord.payload["category"].as_string(), ""))
    return case(
        (raw == "", "unknown"),
        *(
            (or_(*(raw.ilike("%" + word + "%") for word in words)), name)
            for name, words in ALIASES.items()
        ),
        else_="other",
    )


def market_predicates(
    mode,
    *,
    venue=None,
    status=None,
    family=None,
    q=None,
    venues=None,
    category=None,
    category_group=None,
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
    if category_group is not None:
        predicates.append(category_expression() == category_group)
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


def result_market_filter(mode, ids, *, venue=None, category_group=None, q=None):
    return (
        select(MarketRecord.key)
        .where(
            *market_predicates(mode, venue=venue, category_group=category_group, q=q),
            or_(*(MarketRecord.id == mid for mid in ids)),
        )
        .exists()
    )


class CatalogQueries:
    def __init__(self, database, *, allow_file_reviews=False, venues=None, settings=None):
        self.database = database
        self.settings = settings
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
        fields = [
            name
            for name in MarketSummary.model_fields
            if name not in ("counterpart_count", "assessment_state")
        ]
        query = select(
            *(
                (
                    MarketRecord.payload[field].as_string()
                    if field not in ("feed_origin", "ingestion_issues")
                    else MarketRecord.payload[field]
                    if field == "ingestion_issues"
                    else func.coalesce(MarketRecord.payload[field].as_string(), "exchange")
                ).label(field)
                for field in fields
            )
        )
        query = query.where(*market_predicates(mode, venues=self.venues, **filters))
        async with self.database.sessions() as session:
            rows = (
                (await session.execute(query.order_by(MarketRecord.id).limit(limit).offset(offset)))
                .mappings()
                .all()
            )
        summaries = [
            MarketSummary.model_validate(
                {**dict(row), "ingestion_issues": row["ingestion_issues"] or ()}
            )
            for row in rows
        ]
        ids = [m.id for m in summaries]
        if not ids:
            return summaries
        matches = await self.matches(mode, limit=None, market_ids=ids)
        counts = {mid: 0 for mid in ids}
        states = dict.fromkeys(ids, "pending")
        for match in matches:
            for mid in (match.left_id, match.right_id):
                if mid in counts and match.relationship != "mismatch" and not match.operator_veto:
                    counts[mid] += 1
                if (
                    mid in states
                    and match.qualification
                    and match.qualification.status not in ("pending", "stale", "unavailable")
                ):
                    states[mid] = "assessed"
        from arbbot.matching.classification import summary
        from arbbot.storage.models import ClassificationJobRecord

        async with self.database.sessions() as session:
            session.info["classification_identity_cache"] = {}
            jobs = (
                await session.scalars(
                    select(ClassificationJobRecord).where(
                        ClassificationJobRecord.mode == mode,
                        or_(
                            *(
                                ClassificationJobRecord.request["state"]["markets"][i]["id"]
                                .as_string()
                                .in_(ids)
                                for i in (0, 1)
                            )
                        ),
                    )
                )
            ).all()
            for job in jobs:
                advice = await summary(session, job)
                for market in job.request["state"]["markets"]:
                    mid = market["id"]
                    if mid in states:
                        if advice.state == "fresh":
                            states[mid] = "assessed"
                        elif advice.state == "unavailable" and states[mid] != "assessed":
                            states[mid] = "unavailable"
        return [
            m.model_copy(
                update={"counterpart_count": counts[m.id], "assessment_state": states[m.id]}
            )
            for m in summaries
        ]

    async def matches(
        self,
        mode,
        *,
        limit=100,
        offset=0,
        status=None,
        category=None,
        category_group=None,
        relationship=None,
        exclude_mismatch=False,
        historical=False,
        same_event=None,
        market_status=None,
        exclude_rejected=False,
        evidence=None,
        classification=None,
        qualification=None,
        market_id=None,
        market_ids=None,
        match_id=None,
        venue=None,
        family=None,
        q=None,
    ):
        query = select(MatchRecord).where(MatchRecord.mode == mode)
        if not historical:
            query = query.where(MatchRecord.current.is_(True))
        elif match_id is None:
            query = query.where(MatchRecord.current.is_(False))
        if market_id is not None:
            query = query.where(
                or_(
                    MatchRecord.payload["left_id"].as_string() == market_id,
                    MatchRecord.payload["right_id"].as_string() == market_id,
                )
            )
        if market_ids is not None:
            query = query.where(
                or_(
                    *(
                        MatchRecord.payload[side].as_string().in_(market_ids)
                        for side in ("left_id", "right_id")
                    )
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
            query = query.where(
                or_(
                    MatchRecord.payload["status"].as_string().in_({status, "verified"}),
                    MatchRecord.payload["qualification"]["status"].as_string().is_not(None),
                )
            )
        if evidence is not None:
            query = query.where(MatchRecord.evidence_complete.is_(evidence == "complete"))
        if any(
            value is not None
            for value in (venue, family, q, market_status, category, category_group)
        ):
            # All market-side filters must match the same leg. EXISTS avoids duplicated pairs.
            matching_leg = (
                select(MarketRecord.key)
                .where(
                    *market_predicates(
                        mode,
                        venue=venue,
                        family=family,
                        q=q,
                        status=market_status,
                        category=category,
                        category_group=category_group,
                    ),
                    or_(
                        MarketRecord.id == MatchRecord.payload["left_id"].as_string(),
                        MarketRecord.id == MatchRecord.payload["right_id"].as_string(),
                    ),
                )
                .exists()
            )
            query = query.where(matching_leg)
        from arbbot.matching.classification import configured_state, summary
        from arbbot.matching.classification_models import ClassificationSummary
        from arbbot.reviews.provider import refresh_match
        from arbbot.reviews.repository import ReviewRepository
        from arbbot.storage.models import ClassificationJobRecord

        fallback = configured_state(self.settings) if self.settings else "unconfigured"
        reviews = ReviewRepository(self.database)
        special, included, ranks = {}, [], {0: [], 1: [], 2: [], 3: []}
        advisory = MatchRecord.payload["classification"]
        requires_validation = or_(
            relationship is not None or exclude_mismatch or historical,
            MatchRecord.payload["status"].as_string() == "verified",
            MatchRecord.payload["qualification"]["status"].as_string().is_not(None),
            advisory["run_id"].as_string().is_not(None),
            advisory["supports_candidate"].as_boolean().is_(True),
            MatchRecord.payload["ai_only"].as_boolean().is_(True),
        )
        async with reviews._read() as session:
            session.info["classification_identity_cache"] = {}
            rows = (await session.scalars(query.where(requires_validation))).all()
            # Revalidate only approvals and actual advisory results. Ordinary title
            # suggestions need no per-row evidence reads to rank or paginate.
            for row in rows:
                if historical:
                    match = Match.model_validate(row.payload).model_copy(
                        update={"historical": True}
                    )
                    changes = {}
                    if match.classification:
                        changes["classification"] = match.classification.model_copy(
                            update={"state": "stale", "supports_candidate": False}
                        )
                    if match.qualification:
                        changes["qualification"] = match.qualification.model_copy(
                            update={
                                "status": "stale",
                                "blocked_reasons": (
                                    *match.qualification.blocked_reasons,
                                    "explicit_historical_match",
                                ),
                            }
                        )
                    match = match.model_copy(update=changes)
                    if relationship is None or relationship == "unverified":
                        special[row.id] = match
                        included.append(row.id)
                    continue
                match = await refresh_match(
                    reviews,
                    session,
                    mode,
                    Match.model_validate(row.payload),
                    allow_file_reviews=self.allow_file_reviews,
                )
                job = await session.get(ClassificationJobRecord, f"{mode}:{match.id}")
                advice = await summary(session, job) if job else match.classification
                if fallback != "pending" and self.settings:
                    advice = (advice or ClassificationSummary(state=fallback)).model_copy(
                        update={"state": fallback, "supports_candidate": False}
                    )
                match = match.model_copy(update={"classification": advice})
                special[row.id] = match
                if match.ai_only and (not advice or not advice.supports_candidate):
                    continue
                if relationship is not None and match.relationship != relationship:
                    continue
                if exclude_mismatch and match.relationship == "mismatch":
                    continue
                if status is not None and match.status != status:
                    continue
                if classification and (
                    not advice
                    or (classification == "suggested" and not advice.supports_candidate)
                    or (classification != "suggested" and advice.state != classification)
                ):
                    continue
                if qualification and (
                    not match.qualification or match.qualification.status != qualification
                ):
                    continue
                if exclude_rejected and match.status == "rejected":
                    continue
                if same_event is not None and (
                    not match.comparison or match.comparison.same_event != same_event
                ):
                    continue
                included.append(row.id)
                rank = (
                    0
                    if match.status == "verified"
                    else 1
                    if match.comparison and match.comparison.same_event
                    else 2
                    if advice and advice.supports_candidate
                    else 3
                )
                ranks[rank].append(row.id)
            ordinary = MatchRecord.id.not_in(special)
            if qualification:
                ordinary = and_(
                    ordinary,
                    MatchRecord.payload["qualification"]["status"].as_string() == qualification,
                )
            if status is not None:
                ordinary = and_(ordinary, MatchRecord.payload["status"].as_string() == status)
            if classification:
                ordinary = and_(
                    ordinary,
                    advisory["supports_candidate"].as_boolean().is_(True)
                    if classification == "suggested"
                    else func.coalesce(advisory["state"].as_string(), fallback) == classification,
                )
            if exclude_rejected:
                ordinary = and_(ordinary, MatchRecord.payload["status"].as_string() != "rejected")
            if same_event is not None:
                ordinary = and_(
                    ordinary,
                    MatchRecord.payload["comparison"]["same_event"].as_boolean().is_(same_event),
                )
            final = query.where(or_(MatchRecord.id.in_(included), ordinary))
            ordinary_rank = case(
                (MatchRecord.payload["status"].as_string() == "verified", 0),
                (MatchRecord.payload["comparison"]["same_event"].as_boolean().is_(True), 1),
                (advisory["supports_candidate"].as_boolean().is_(True), 2),
                else_=3,
            )
            rank = (
                case(
                    *[(MatchRecord.id.in_(ids), value) for value, ids in ranks.items() if ids],
                    else_=ordinary_rank,
                )
                if any(ranks.values())
                else ordinary_rank
            )
            rows = (
                await session.scalars(
                    final.order_by(
                        rank,
                        case(
                            (
                                MatchRecord.id.in_(
                                    [
                                        mid
                                        for mid, match in special.items()
                                        if match.classification
                                        and match.classification.state == "fresh"
                                    ]
                                ),
                                advisory["event"]["confidence"].as_float(),
                            ),
                            else_=0,
                        ).desc(),
                        MatchRecord.id,
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            results = []
            for row in rows:
                match = special.get(row.id) or Match.model_validate(row.payload)
                if not match.classification:
                    match = match.model_copy(
                        update={"classification": ClassificationSummary(state=fallback)}
                    )
                results.append(match)
            return results
