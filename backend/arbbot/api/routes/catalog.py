from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from arbbot.discovery.models import CatalogObservation
from arbbot.domain import Market, MarketSummary, Match, Venue
from arbbot.storage.catalog_queries import CatalogQueries
from arbbot.storage.models import CatalogInventoryRecord, CatalogObservationRecord
from arbbot.storage.repository import aware

PageSize = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Search = Annotated[str | None, Query(min_length=1, max_length=200)]
Family = Annotated[str | None, Query(min_length=1, max_length=100)]


def catalog_router(database, mode, *, allow_file_reviews=False, venues=None, settings=None):
    router = APIRouter(prefix="/api/v1")
    catalog = CatalogQueries(
        database, allow_file_reviews=allow_file_reviews, venues=venues, settings=settings
    )

    from arbbot.execution.models import AccessSummary
    from arbbot.execution.repository import ExecutionRepository

    @router.get("/access-summary", response_model=AccessSummary)
    async def accessSummary():
        from arbbot.domain import utcnow

        async with database.sessions() as session:
            current = await ExecutionRepository(database).current(
                session, f"{mode}:access:installation"
            )
        if not current:
            return AccessSummary(status="unknown")
        value = current.value
        status = "expired" if value.expires_at <= utcnow() else value.status
        return AccessSummary(
            status=status,
            revision_id=current.id,
            permitted_venues=tuple(p.venue for p in value.permissions)
            if status == "verified"
            else (),
            expires_at=value.expires_at,
        )

    @router.get("/catalog/inventory", response_model=list[CatalogObservation])
    async def inventory(
        limit: PageSize = 100,
        offset: Offset = 0,
        venue: Venue | None = None,
        supported: bool | None = None,
    ):
        query = (
            select(CatalogInventoryRecord, CatalogObservationRecord)
            .join(
                CatalogObservationRecord,
                CatalogInventoryRecord.observation_id == CatalogObservationRecord.id,
            )
            .where(CatalogInventoryRecord.mode == mode)
        )
        if venues is not None:
            query = query.where(CatalogInventoryRecord.venue.in_(venues))
        if venue is not None:
            query = query.where(CatalogInventoryRecord.venue == venue)
        if supported is not None:
            query = query.where(CatalogInventoryRecord.supported == supported)
        async with database.sessions() as session:
            rows = (
                await session.execute(
                    query.order_by(CatalogInventoryRecord.key).limit(limit).offset(offset)
                )
            ).all()
        return [
            CatalogObservation(
                venue=row.venue,
                external_id=row.external_id,
                observation_id=row.observation_id,
                market_id=row.market_id,
                supported=row.supported,
                reason=row.reason,
                observed_at=aware(row.observed_at),
                raw=observation.payload,
            )
            for row, observation in rows
        ]

    @router.get("/market-summaries", response_model=list[MarketSummary])
    async def marketSummaries(
        limit: PageSize = 100,
        offset: Offset = 0,
        venue: Venue | None = None,
        status: Literal["open", "closed"] | None = None,
        category: Family = None,
        q: Search = None,
    ):
        return await catalog.summaries(
            mode, limit=limit, offset=offset, venue=venue, status=status, category=category, q=q
        )

    @router.get("/markets", response_model=list[Market])
    async def markets(
        limit: PageSize = 100,
        offset: Offset = 0,
        venue: Venue | None = None,
        status: Literal["open", "closed"] | None = None,
        family: Family = None,
        q: Search = None,
    ):
        return await catalog.markets(
            mode, limit=limit, offset=offset, venue=venue, status=status, family=family, q=q
        )

    @router.get("/matches", response_model=list[Match])
    async def matches(
        limit: PageSize = 100,
        offset: Offset = 0,
        venue: Venue | None = None,
        status: Literal["candidate", "verified", "rejected"] | None = None,
        family: Family = None,
        q: Search = None,
        evidence: Literal["complete", "incomplete"] | None = None,
        classification: Literal[
            "suggested", "fresh", "pending", "stale", "unavailable", "unconfigured", "disabled"
        ]
        | None = None,
        market_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    ):
        return await catalog.matches(
            mode,
            limit=limit,
            offset=offset,
            venue=venue,
            status=status,
            family=family,
            q=q,
            evidence=evidence,
            classification=classification,
            market_id=market_id,
        )

    @router.get("/matches/{match_id}", response_model=Match)
    async def match(match_id: str):
        rows = await catalog.matches(mode, match_id=match_id, limit=1)
        if not rows:
            raise HTTPException(404, "Current match not found")
        return rows[0]

    from arbbot.matching.classification import summary
    from arbbot.matching.classification_models import ClassificationRun, ClassificationSummary
    from arbbot.storage.models import ClassificationJobRecord, ClassificationRunRecord

    @router.get("/matches/{match_id}/classification", response_model=ClassificationSummary)
    async def classification_detail(
        match_id: str,
        run_id: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ):
        async with database.sessions() as session:
            if run_id:
                row = await session.get(ClassificationRunRecord, run_id)
                if not row or row.mode != mode or row.match_id != match_id:
                    raise HTTPException(404, "Classification run not found")
                value = ClassificationRun.model_validate(row.payload).summary
                return value.model_copy(
                    update={
                        "state": "stale",
                        "supports_candidate": False,
                        "limitations": (
                            *value.limitations,
                            "Explicit historical result; not current advice.",
                        ),
                    }
                )
            job = await session.get(ClassificationJobRecord, f"{mode}:{match_id}")
            if job:
                value = await summary(session, job)
                if settings:
                    from arbbot.matching.classification import configured_state

                    state = configured_state(settings)
                    if state != "pending":
                        value = value.model_copy(
                            update={"state": state, "supports_candidate": False}
                        )
                return value
        rows = await catalog.matches(mode, match_id=match_id, limit=1)
        if not rows:
            raise HTTPException(404, "Current match not found")
        return rows[0].classification or ClassificationSummary(state="unconfigured")

    return router
