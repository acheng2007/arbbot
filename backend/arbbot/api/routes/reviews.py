"""Authenticated review revisions with optimistic concurrency and audit history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from arbbot.auth.dependencies import require_reviewer, require_viewer
from arbbot.auth.service import Principal
from arbbot.reviews.models import (
    Actor,
    DecisionRevision,
    DecisionState,
    DecisionWrite,
    DraftRevision,
    DraftWrite,
    ReviewValidationError,
    RevisionConflict,
)
from arbbot.reviews.repository import ReviewRepository
from arbbot.storage.repository import Repository

Viewer = Annotated[Principal, Depends(require_viewer)]
Reviewer = Annotated[Principal, Depends(require_reviewer)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]


async def review_operation(operation):
    try:
        return await operation
    except LookupError:
        raise HTTPException(404, "Review input not found in this data mode") from None
    except RevisionConflict as exc:
        raise HTTPException(
            409,
            {
                "code": "revision_conflict",
                "message": str(exc),
                "current_revision_id": exc.current_revision_id,
                "issues": list(exc.issues),
            },
        ) from None
    except ReviewValidationError as exc:
        raise HTTPException(
            422,
            {
                "code": "invalid_review_evidence",
                "issues": list(exc.issues),
            },
        ) from None


def reviews_router(database, mode):
    router = APIRouter(prefix="/api/v1", tags=["reviews"])
    reviews = ReviewRepository(database)
    markets = Repository(database)

    async def market_exists(market_id):
        if await markets.market(mode, market_id) is None:
            raise HTTPException(404, "Market not found in this data mode")

    @router.get("/markets/{market_id}/draft", response_model=DraftRevision | None)
    async def current_draft(market_id: str, principal: Viewer):
        await market_exists(market_id)
        return await reviews.current_draft(mode, market_id)

    @router.get("/markets/{market_id}/drafts", response_model=list[DraftRevision])
    async def draft_history(
        market_id: str, principal: Viewer, limit: Limit = 20, offset: Offset = 0
    ):
        await market_exists(market_id)
        return await reviews.draft_history(mode, market_id, limit=limit, offset=offset)

    @router.get("/drafts/{revision_id}", response_model=DraftRevision)
    async def draft_revision(revision_id: str, principal: Viewer):
        return await review_operation(reviews.draft_revision(mode, revision_id))

    @router.post("/markets/{market_id}/drafts", response_model=DraftRevision, status_code=201)
    async def save_draft(market_id: str, body: DraftWrite, principal: Reviewer):
        actor = Actor(issuer=principal.issuer, subject=principal.subject)
        return await review_operation(reviews.save_draft(mode, market_id, body, actor))

    @router.get("/reviews/current", response_model=DecisionState | None)
    async def current_review(left_id: str, right_id: str, principal: Viewer):
        await market_exists(left_id)
        await market_exists(right_id)
        return await reviews.current_decision(mode, left_id, right_id)

    @router.get("/reviews/history", response_model=list[DecisionRevision])
    async def review_history(
        left_id: str, right_id: str, principal: Viewer, limit: Limit = 20, offset: Offset = 0
    ):
        await market_exists(left_id)
        await market_exists(right_id)
        return await reviews.decision_history(mode, left_id, right_id, limit=limit, offset=offset)

    @router.post("/reviews", response_model=DecisionRevision, status_code=201)
    async def save_review(body: DecisionWrite, principal: Reviewer):
        actor = Actor(issuer=principal.issuer, subject=principal.subject)
        return await review_operation(reviews.save_decision(mode, body, actor))

    return router
