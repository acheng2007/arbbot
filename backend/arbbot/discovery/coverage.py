"""Current, filtered coverage. Reads never poll venues or call a model."""

from collections import defaultdict

from sqlalchemy import func, select

from arbbot.discovery.models import CoverageGroup, DiscoveryCoverage, RetrievalHealth
from arbbot.discovery.service import catalog_reports
from arbbot.domain import utcnow
from arbbot.storage.catalog_queries import market_predicates
from arbbot.storage.models import (
    CatalogInventoryRecord,
    ClassificationJobRecord,
    MarketRecord,
    RetrievalStateRecord,
)


async def coverage(
    catalog,
    settings,
    *,
    venue=None,
    category_group=None,
    category=None,
    q=None,
    relationship=None,
    historical=False,
    status=None,
    exclude_mismatch=False,
    exclude_rejected=False,
):
    from arbbot.discovery.categories import category_group as normalize_category

    mode, now = settings.mode, utcnow()
    matches = await catalog.matches(
        mode,
        limit=None,
        venue=venue,
        category_group=category_group,
        category=category,
        q=q,
        relationship=relationship,
        historical=historical,
        market_status=status,
        exclude_mismatch=exclude_mismatch,
        exclude_rejected=exclude_rejected,
    )
    groups, indexed = {}, {}
    async with catalog.database.sessions() as session:
        records = (
            await session.scalars(
                select(MarketRecord).where(
                    *market_predicates(
                        mode,
                        venues=catalog.venues,
                        venue=venue,
                        category_group=category_group,
                        category=category,
                        q=q,
                        status=status,
                    )
                )
            )
        ).all()
        retrieval = await session.get(RetrievalStateRecord, mode)
        excluded = await session.scalar(
            select(func.count())
            .select_from(CatalogInventoryRecord)
            .where(
                CatalogInventoryRecord.mode == mode,
                CatalogInventoryRecord.supported.is_(False),
                *([CatalogInventoryRecord.venue == venue] if venue else []),
            )
        )
    for row in records:
        group = (row.venue, normalize_category(row.payload.get("category")))
        groups.setdefault(
            group,
            {
                "contracts": 0,
                "paired": set(),
                "assessed": set(),
                "verified": set(),
                "incomplete": set(),
                "mismatch": set(),
                "fresh_books": 0,
                "blockers": defaultdict(int),
            },
        )
        groups[group]["contracts"] += 1
        indexed[row.id] = group
    from arbbot.matching.classification import classification_health, summary

    async with catalog.database.sessions() as session:
        session.info["classification_identity_cache"] = {}
        jobs = (
            await session.scalars(
                select(ClassificationJobRecord).where(
                    ClassificationJobRecord.mode == mode,
                )
            )
        ).all()
        for job in jobs:
            advice = await summary(session, job)
            if advice.state == "fresh":
                for market in job.request["state"]["markets"]:
                    mid = market["id"]
                    if mid in indexed:
                        groups[indexed[mid]]["assessed"].add(mid)
    provider_health = await classification_health(catalog.database, settings)
    # Health is independent from SSE connectivity and semantic assessment.
    from arbbot.storage.repository import Repository

    for health in await Repository(catalog.database).health(mode, settings.health_timeout_seconds):
        for market in health.get("market_health", []):
            mid = market.get("market_id")
            if mid in indexed and market.get("status") == "healthy" and health["status"] != "stale":
                groups[indexed[mid]]["fresh_books"] += 1
    for match in matches:
        for mid in (match.left_id, match.right_id):
            if mid not in indexed:
                continue
            group = groups[indexed[mid]]
            group["paired"].add(mid)
            advice = match.classification
            assessment = match.qualification
            if (advice and advice.state == "fresh") or (
                assessment and assessment.status not in ("pending", "stale", "unavailable")
            ):
                group["assessed"].add(mid)
            if match.relationship in ("verified", "mismatch"):
                group[match.relationship].add(mid)
            if assessment:
                if assessment.status == "incomplete":
                    group["incomplete"].add(mid)
                for reason in assessment.blocked_reasons:
                    group["blockers"][reason] += 1
    data = {}
    if retrieval:
        data = {k: v for k, v in retrieval.payload.items() if k in RetrievalHealth.model_fields}
        data["updated_at"] = retrieval.updated_at
    return DiscoveryCoverage(
        as_of=now,
        contracts=len(records),
        comparisons=len(matches),
        unverified=sum(m.relationship == "unverified" for m in matches),
        verified=sum(m.relationship == "verified" for m in matches),
        mismatch=sum(m.relationship == "mismatch" for m in matches),
        pending=sum(not m.classification or m.classification.state == "pending" for m in matches),
        groups=tuple(
            CoverageGroup(
                venue=venue,
                category=category,
                contracts=value["contracts"],
                with_counterparts=len(value["paired"]),
                assessed=len(value["assessed"]),
                verified=len(value["verified"]),
                incomplete=len(value["incomplete"]),
                mismatch=len(value["mismatch"]),
                fresh_books=value["fresh_books"],
                blockers=dict(
                    sorted(value["blockers"].items(), key=lambda pair: (-pair[1], pair[0]))[:10]
                ),
            )
            for (venue, category), value in sorted(groups.items())
        ),
        retrieval=RetrievalHealth(**data),
        catalogs=tuple(await catalog_reports(catalog.database, mode)),
        excluded_instruments=excluded,
        model_state=provider_health["state"],
        queued_pairs=provider_health["queued"],
        last_model_success=provider_health["last_success"],
    )
