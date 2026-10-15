from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from arbbot.domain import PotentialOpportunity
from arbbot.qualification.models import Assessment
from arbbot.qualification.potential import query
from arbbot.qualification.service import current
from arbbot.qualification.summary import QualificationSummary
from arbbot.storage.models import MatchRecord, QualificationRunRecord


def qualification_router(repository, settings):
    router = APIRouter(prefix="/api/v1")
    database, mode = repository.database, settings.mode

    @router.get("/matches/{match_id}/qualification", response_model=QualificationSummary)
    async def qualification(
        match_id: str,
        assessment_id: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ):
        async with database.sessions() as session:
            if assessment_id:
                row = await session.get(QualificationRunRecord, assessment_id)
                if not row or row.mode != mode or row.match_id != match_id:
                    raise HTTPException(404, "Qualification assessment not found")
                value = Assessment.model_validate(row.payload).summary
                return value.model_copy(
                    update={
                        "status": "stale",
                        "blocked_reasons": (
                            *value.blocked_reasons,
                            "explicit_historical_assessment",
                        ),
                    }
                )
            match = await session.get(MatchRecord, match_id)
            if not match or match.mode != mode or not match.current:
                raise HTTPException(404, "Current match not found")
            value, _ = await current(session, mode, match_id)
            return value

    @router.get("/matches/{match_id}/qualification/history", response_model=list[Assessment])
    async def qualification_history(
        match_id: str,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    ):
        async with database.sessions() as session:
            rows = await session.scalars(
                select(QualificationRunRecord)
                .where(
                    QualificationRunRecord.mode == mode, QualificationRunRecord.match_id == match_id
                )
                .order_by(QualificationRunRecord.completed_at.desc(), QualificationRunRecord.id)
                .limit(limit)
                .offset(offset)
            )
            return [Assessment.model_validate(row.payload) for row in rows]

    @router.get("/potential-opportunities", response_model=list[PotentialOpportunity])
    async def potential_opportunities(
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    ):
        return await query(repository, settings, limit=limit, offset=offset)

    @router.get("/potential-opportunities/{potential_id}", response_model=PotentialOpportunity)
    async def potential_opportunity(potential_id: str, historical: bool = False):
        rows = await query(repository, settings, item_id=potential_id, history=historical, limit=1)
        if not rows:
            raise HTTPException(404, "Potential opportunity not found")
        return rows[0]

    return router
