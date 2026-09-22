from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from arbbot.auth.service import IdentityUnavailable, InvalidCredentials, Principal

bearer = HTTPBearer(auto_error=False, description="RFC 9068 access token for the Arbbot API")


async def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None or len(request.headers.getlist("authorization")) != 1:
        raise HTTPException(
            401, "Bearer credentials required", headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        return await request.app.state.authenticator.verify(credentials.credentials)
    except InvalidCredentials:
        raise HTTPException(
            401, "Invalid access token", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except IdentityUnavailable:
        raise HTTPException(503, "Identity verification unavailable") from None


async def require_viewer(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
    if "viewer" not in principal.roles:
        raise HTTPException(403, "Viewer permission required")
    return principal


async def require_reviewer(
    request: Request,
    principal: Annotated[Principal, Depends(current_principal)],
) -> Principal:
    if "reviewer" not in principal.roles:
        raise HTTPException(403, "Reviewer permission required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origins = request.headers.getlist("origin")
        if len(origins) > 1 or (origins and origins[0] not in request.app.state.auth_origins):
            raise HTTPException(403, "Mutation origin not allowed")
        if not origins and request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Mutation origin required")
    return principal
