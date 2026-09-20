import asyncio
import json
import time
from typing import Literal

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, computed_field

from arbbot.domain import digest


class InvalidCredentials(Exception):
    pass


class IdentityUnavailable(Exception):
    pass


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    issuer: str
    subject: str
    client_id: str
    roles: frozenset[Literal["viewer", "reviewer"]]

    @computed_field
    @property
    def audit_id(self) -> str:
        return digest([self.issuer, self.subject])


class Authenticator:
    def __init__(self, settings, client=None, *, clock=time.monotonic):
        self.settings = settings
        self.client = client
        self.clock = clock
        self.keys = {}
        self.expires = 0
        self.last_attempt = float("-inf")
        self.lock = asyncio.Lock()

    async def close(self):
        if self.client is not None:
            await self.client.aclose()

    async def key(self, kid):
        async with self.lock:
            now = self.clock()
            if now < self.expires and kid in self.keys:
                return self.keys[kid]
            if now - self.last_attempt < self.settings.auth_refresh_seconds:
                if now >= self.expires:
                    raise IdentityUnavailable
                raise InvalidCredentials
            self.last_attempt = now
            if self.client is None:
                self.client = httpx.AsyncClient(
                    timeout=5,
                    follow_redirects=False,
                    limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
                )
            try:
                async with self.client.stream("GET", self.settings.auth_jwks_url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 262144:
                            raise ValueError("JWKS exceeds limit")
                document = json.loads(body)
                items = document["keys"]
                if not isinstance(items, list) or not 1 <= len(items) <= 64:
                    raise ValueError("Invalid key set")
                keys = {}
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid key")
                    if (
                        item.get("kty") != "RSA"
                        or item.get("alg", "RS256") != "RS256"
                        or item.get("use", "sig") != "sig"
                    ):
                        continue
                    if "key_ops" in item and item["key_ops"] != ["verify"]:
                        continue
                    name = item.get("kid")
                    if (
                        not isinstance(name, str)
                        or not 1 <= len(name) <= 256
                        or name in keys
                        or "d" in item
                    ):
                        raise ValueError("Invalid signing key identifier")
                    key = jwt.PyJWK.from_dict(item, algorithm="RS256").key
                    if not 2048 <= key.key_size <= 8192:
                        raise ValueError("Unsupported signing key size")
                    keys[name] = key
                if not keys:
                    raise ValueError("No supported signing keys")
            except (httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError) as exc:
                raise IdentityUnavailable from exc
            self.keys = keys
            self.expires = self.clock() + self.settings.auth_jwks_ttl_seconds
            if kid not in keys:
                raise InvalidCredentials
            return keys[kid]

    async def verify(self, token: str) -> Principal:
        if not self.settings.auth_issuer:
            raise IdentityUnavailable
        try:
            if len(token) > 16384:
                raise InvalidCredentials
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("typ") not in {
                "at+jwt",
                "application/at+jwt",
            }:
                raise InvalidCredentials
            if header.get("crit") or "jku" in header or "x5u" in header:
                raise InvalidCredentials
            kid = header.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 256:
                raise InvalidCredentials
            key = await self.key(kid)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.settings.auth_audience,
                issuer=self.settings.auth_issuer,
                leeway=self.settings.auth_clock_skew_seconds,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "client_id", "jti"]},
            )
            for name in ("sub", "client_id", "jti"):
                if not isinstance(claims[name], str) or not 1 <= len(claims[name].strip()) <= 512:
                    raise InvalidCredentials
            for name in ("exp", "iat", "nbf"):
                if name in claims and type(claims[name]) is not int:
                    raise InvalidCredentials
            if not 0 < claims["exp"] - claims["iat"] <= self.settings.auth_max_token_seconds:
                raise InvalidCredentials
            scope = claims.get("scope", "")
            if not isinstance(scope, str) or len(scope) > 2048:
                raise InvalidCredentials
            scopes = set(scope.split())
            roles = set()
            if "arbbot:read" in scopes:
                roles.add("viewer")
            if "arbbot:review" in scopes:
                roles.update(("viewer", "reviewer"))
            return Principal(
                issuer=claims["iss"],
                subject=claims["sub"],
                client_id=claims["client_id"],
                roles=frozenset(roles),
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise InvalidCredentials from exc
