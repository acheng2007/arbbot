from typing import Annotated, Literal

from fastapi import APIRouter, Query

from arbbot.domain import Market, Match, Venue
from arbbot.storage.catalog_queries import CatalogQueries

PageSize = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Search = Annotated[str | None, Query(min_length=1, max_length=200)]
Family = Annotated[str | None, Query(min_length=1, max_length=100)]


def catalog_router(database, mode, *, allow_file_reviews=False):
    router = APIRouter(prefix="/api/v1")
    catalog = CatalogQueries(database, allow_file_reviews=allow_file_reviews)

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
        )

    return router
