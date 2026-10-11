"""Public evidence provenance, with bounded metadata lists and explicit downloads."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from arbbot.sources.models import SourceArtifactSummary
from arbbot.sources.repository import SourceRepository
from arbbot.sources.text import DerivedText, derive_text
from arbbot.storage.repository import Repository


def sources_router(database, mode):
    router = APIRouter()
    sources = SourceRepository(database)
    markets = Repository(database)

    @router.get("/api/v1/markets/{market_id}/sources", response_model=list[SourceArtifactSummary])
    async def source_history(
        market_id: str,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    ):
        if await markets.market(mode, market_id) is None:
            raise HTTPException(404, "Market not found")
        return await sources.summaries(mode, market_id, limit=limit, offset=offset)

    @router.get("/api/v1/sources/{artifact_id}/content", response_class=Response)
    async def source_content(artifact_id: str):
        result = await sources.get(mode, artifact_id)
        if result is None or result.content is None:
            raise HTTPException(404, "Captured source not found")
        return Response(
            result.content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": 'attachment; filename="settlement-source"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{result.content_digest}"',
            },
        )

    @router.get("/api/v1/sources/{artifact_id}/text", response_model=DerivedText)
    async def source_text(artifact_id: str):
        result = await sources.get(mode, artifact_id)
        if result is None or result.content is None:
            raise HTTPException(404, "Captured source not found")
        return await derive_text(result.content, result.content_type, result.id)

    return router
