import asyncio
import json
import time
from typing import Annotated

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends
from pydantic import ValidationError

from arbbot.api.app import create_app
from arbbot.auth.dependencies import require_reviewer
from arbbot.auth.service import Authenticator, IdentityUnavailable, InvalidCredentials, Principal
from arbbot.config import Settings
from arbbot.domain import digest

ISSUER = "https://identity.example.test/"
AUDIENCE = "arbbot-api"


@pytest.fixture(scope="module")
def signing_keys():
    return [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]


def public_key(key, kid="first"):
    return {
        **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
    }


def access_token(key, *, headers=None, remove=(), **claims):
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": "reviewer-123",
        "aud": AUDIENCE,
        "iat": now - 10,
        "exp": now + 60,
        "client_id": "arbbot-web",
        "jti": "test-token-id",
        "scope": "arbbot:read arbbot:review",
        **claims,
    }
    for name in remove:
        del payload[name]
    return jwt.encode(
        payload,
        key,
        algorithm="RS256",
        headers={"kid": "first", "typ": "at+jwt", **(headers or {})},
    )


@pytest.fixture
async def protected_app(database, signing_keys):
    settings, db, _ = database
    settings = Settings(
        database_url=settings.database_url,
        auth_issuer=ISSUER,
        auth_audience=AUDIENCE,
        auth_jwks_url=ISSUER + "jwks",
        _env_file=None,
    )
    app = create_app(settings, db)
    app.state.authenticator.client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"keys": [public_key(signing_keys[0])]})
        )
    )

    @app.post("/test/review")
    async def review(principal: Annotated[Principal, Depends(require_reviewer)]):
        return {"reviewer_id": principal.audit_id, "subject": principal.subject}

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client
    finally:
        await app.state.authenticator.close()


async def test_verified_identity_and_server_derived_audit(protected_app, signing_keys):
    _, client = protected_app
    headers = {
        "Authorization": "Bearer " + access_token(signing_keys[0]),
        "Origin": "http://localhost:3000",
        "X-Reviewer-Id": "forged",
    }
    result = await client.get("/api/v1/auth/me", headers=headers)
    assert result.status_code == 200
    assert set(result.json()["roles"]) == {"viewer", "reviewer"}
    result = await client.post("/test/review", headers=headers, json={"reviewer_id": "forged"})
    assert result.status_code == 200
    assert result.json()["reviewer_id"] == digest([ISSUER, "reviewer-123"])
    assert result.json()["subject"] == "reviewer-123"


async def test_viewer_cannot_review_and_role_headers_are_ignored(protected_app, signing_keys):
    _, client = protected_app
    headers = {
        "Authorization": "Bearer " + access_token(signing_keys[0], scope="arbbot:read"),
        "X-Role": "reviewer",
    }
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
    assert (await client.post("/test/review", headers=headers)).status_code == 403
    headers["Authorization"] = "Bearer " + access_token(signing_keys[0], scope="unrelated")
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 403


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"iss": "https://attacker.test/"},
        {"aud": "another-api"},
        {"sub": ""},
        {"sub": 12},
        {"scope": ["arbbot:review"]},
        {"iat": True},
        {"iat": 1},
        {"exp": "9999999999"},
        {"nbf": 9999999999},
    ],
)
async def test_invalid_claims_fail_closed(protected_app, signing_keys, claims):
    _, client = protected_app
    result = await client.post(
        "/test/review",
        headers={"Authorization": "Bearer " + access_token(signing_keys[0], **claims)},
    )
    assert result.status_code == 401
    assert result.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("name", ["iss", "sub", "aud", "iat", "exp", "client_id", "jti"])
async def test_required_claims(protected_app, signing_keys, name):
    _, client = protected_app
    token = access_token(signing_keys[0], remove=[name])
    assert (
        await client.post("/test/review", headers={"Authorization": "Bearer " + token})
    ).status_code == 401


async def test_missing_cookie_forged_and_id_token_rejected(protected_app, signing_keys):
    _, client = protected_app
    assert (await client.post("/test/review")).status_code == 401
    token = access_token(signing_keys[0])
    assert (
        await client.post("/test/review", headers={"Cookie": "access_token=" + token})
    ).status_code == 401
    for bad in [
        "malformed",
        "x" * 16385,
        access_token(signing_keys[1]),
        access_token(signing_keys[0], headers={"typ": "JWT"}),
        access_token(signing_keys[0], headers={"jku": "https://attacker.test/jwks"}),
        jwt.encode(
            {"sub": "attacker"},
            "synthetic-invalid-hmac-key-32-bytes-long",
            algorithm="HS256",
            headers={"kid": "first", "typ": "at+jwt"},
        ),
    ]:
        assert (
            await client.post("/test/review", headers={"Authorization": "Bearer " + bad})
        ).status_code == 401
    duplicate = [("Authorization", "Bearer " + token), ("Authorization", "Bearer " + token)]
    assert (await client.post("/test/review", headers=duplicate)).status_code == 401


async def test_browser_origins_and_preflights(protected_app, signing_keys):
    _, client = protected_app
    headers = {"Authorization": "Bearer " + access_token(signing_keys[0])}
    for origin in ("https://evil.test", "null"):
        assert (
            await client.post("/test/review", headers={**headers, "Origin": origin})
        ).status_code == 403
        preflight = await client.options(
            "/test/review",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        assert preflight.status_code == 400
        assert "access-control-allow-origin" not in preflight.headers
    assert (
        await client.post("/test/review", headers={**headers, "Sec-Fetch-Site": "cross-site"})
    ).status_code == 403
    allowed = await client.options(
        "/test/review",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in allowed.headers


async def test_unconfigured_identity_keeps_reads_public_but_protected_routes_closed(database):
    settings, db, _ = database
    app = create_app(settings, db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/api/v1/markets")).status_code == 200
        assert (
            await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token"})
        ).status_code == 503


async def test_jwks_cache_rotation_and_outage_fail_closed(signing_keys):
    now = [0.0]
    calls = []
    document = {"keys": [public_key(signing_keys[0])]}
    response_status = [200]

    def serve(request):
        calls.append(str(request.url))
        return httpx.Response(response_status[0], json=document)

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    settings = Settings(
        auth_issuer=ISSUER, auth_audience=AUDIENCE, auth_jwks_url=ISSUER + "jwks", _env_file=None
    )
    auth = Authenticator(settings, client, clock=lambda: now[0])
    try:
        first = access_token(signing_keys[0])
        results = await asyncio.gather(*(auth.verify(first) for _ in range(8)))
        assert len(calls) == 1 and all(r.subject == "reviewer-123" for r in results)
        rotated = access_token(signing_keys[1], headers={"kid": "second"})
        with pytest.raises(InvalidCredentials):
            await auth.verify(rotated)
        assert len(calls) == 1
        now[0] += 31
        document["keys"].append(public_key(signing_keys[1], "second"))
        assert (await auth.verify(rotated)).subject == "reviewer-123"
        assert len(calls) == 2
        now[0] += 301
        response_status[0] = 503
        with pytest.raises(IdentityUnavailable):
            await auth.verify(first)
        with pytest.raises(IdentityUnavailable):
            await auth.verify(first)
        assert len(calls) == 3
        now[0] += 31
        response_status[0] = 200
        document["keys"] = [public_key(signing_keys[1], "second")]
        assert (await auth.verify(rotated)).subject == "reviewer-123"
        with pytest.raises(InvalidCredentials):
            await auth.verify(first)
    finally:
        await auth.close()


@pytest.mark.parametrize(
    "settings",
    [
        {"auth_issuer": ISSUER},
        {"cors_origins": ["*"]},
        {"cors_origins": ["null"]},
        {"auth_refresh_seconds": 31, "auth_jwks_ttl_seconds": 30},
        {
            "auth_issuer": "http://issuer.test",
            "auth_audience": AUDIENCE,
            "auth_jwks_url": ISSUER + "jwks",
        },
    ],
)
def test_invalid_security_configuration(settings):
    with pytest.raises(ValidationError):
        Settings(**settings, _env_file=None)


@pytest.mark.parametrize("case", ["duplicate", "private", "empty", "oversize", "bad-json"])
async def test_unusable_jwks_returns_unavailable_without_disclosing_body(
    protected_app, signing_keys, case
):
    app, client = protected_app
    key = public_key(signing_keys[0])
    payload = {"keys": [key]}
    if case == "duplicate":
        payload["keys"].append(key)
    elif case == "private":
        key["d"] = "private-key-material"
    elif case == "empty":
        payload["keys"] = []
    response = httpx.Response(200, json=payload)
    if case == "oversize":
        response = httpx.Response(200, content=b"x" * 262145)
    if case == "bad-json":
        response = httpx.Response(200, content=b"private-provider-error")
    await app.state.authenticator.client.aclose()
    app.state.authenticator.client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    )
    result = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + access_token(signing_keys[0])}
    )
    assert result.status_code == 503
    assert result.json() == {"detail": "Identity verification unavailable"}
