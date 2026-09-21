"""Bounded evidence reads. No redirects, arbitrary hosts, cookies or credentials."""

import asyncio
import json
from collections import OrderedDict
from time import monotonic

import httpx

from arbbot.domain import utcnow
from arbbot.sources.models import MAX_CONTENT_BYTES, SourceCapture

ALLOWED_HOSTS = frozenset(
    {
        "external-api.kalshi.com",
        "gamma-api.polymarket.com",
        "assets.kalshi.com",
        "kalshi-public-docs.s3.amazonaws.com",
        "kalshi-public-docs.s3.us-east-1.amazonaws.com",
        "www.bls.gov",
        "bls.gov",
    }
)
CONTENT_TYPES = {"application/json", "application/pdf", "text/plain", "text/html"}


class EvidenceError(ValueError):
    pass


class SourceFetcher:
    def __init__(self, *, transport=None, ttl=300):
        self.transport, self.ttl = transport, ttl
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()

    async def read(self, url):
        try:
            parsed = httpx.URL(url)
        except (httpx.InvalidURL, TypeError) as exc:
            raise EvidenceError("invalid_source_url") from exc
        if (
            parsed.scheme != "https"
            or parsed.host not in ALLOWED_HOSTS
            or parsed.port not in (None, 443)
            or parsed.userinfo
            or parsed.query
            or parsed.fragment
        ):
            raise EvidenceError("source_url_not_allowed")
        # Bound concurrency, cache size, response size, retries and elapsed time.
        async with self.lock:
            cached = self.cache.get(url)
            if cached and monotonic() - cached[0] < self.ttl:
                return cached[1:]
            async with asyncio.timeout(20):
                async with httpx.AsyncClient(
                    timeout=5, follow_redirects=False, trust_env=False, transport=self.transport
                ) as client:
                    for attempt in range(3):
                        try:
                            async with client.stream("GET", url) as response:
                                if response.status_code in {429, 500, 502, 503, 504}:
                                    raise httpx.TransportError("retryable_response")
                                if response.status_code != 200:
                                    raise EvidenceError(f"source_http_{response.status_code}")
                                content_type = (
                                    response.headers.get("content-type", "").split(";")[0].lower()
                                )
                                if content_type not in CONTENT_TYPES:
                                    raise EvidenceError("unsupported_content_type")
                                data = bytearray()
                                async for chunk in response.aiter_bytes():
                                    if len(data) + len(chunk) > MAX_CONTENT_BYTES:
                                        raise EvidenceError("response_too_large")
                                    data.extend(chunk)
                                if not data:
                                    raise EvidenceError("empty_source")
                                result = (bytes(data), content_type, utcnow())
                                self.cache[url] = (monotonic(), *result)
                                self.cache.move_to_end(url)
                                while len(self.cache) > 128:
                                    self.cache.popitem(last=False)
                                return result
                        except httpx.TransportError:
                            if attempt == 2:
                                raise EvidenceError("source_transport_failure") from None
                            await asyncio.sleep(0.1 * 2**attempt)


class EvidenceCollector:
    def __init__(self, market, repository, fetcher):
        self.market, self.repository, self.fetcher = market, repository, fetcher
        self.references, self.issues = [], []
        self.documents = []

    async def get(self, url, *, json_document=False):
        try:
            content, content_type, retrieved_at = await self.fetcher.read(url)
            capture = SourceCapture(
                mode=self.market.mode,
                market_id=self.market.id,
                venue=self.market.venue,
                url=url,
                retrieved_at=retrieved_at,
                status="success",
                content=content,
                content_type=content_type,
            )
            saved = await self.repository.save(capture)
            self.references.append({"url": str(saved.url), "digest": saved.content_digest})
            if not json_document:
                self.documents.append({"url": str(saved.url), "digest": saved.content_digest})
            if json_document:
                if content_type != "application/json":
                    raise EvidenceError("expected_json")
                try:
                    result = json.loads(content, parse_float=str)
                except (ValueError, UnicodeError) as exc:
                    raise EvidenceError("malformed_json") from exc
                if not isinstance(result, dict):
                    raise EvidenceError("expected_json_object")
                return result
            return content
        except (EvidenceError, TimeoutError) as exc:
            code = str(exc) if isinstance(exc, EvidenceError) else "source_timeout"
            self.issues.append(code)
            # Invalid/credentialed URLs are never persisted or echoed in errors.
            if code not in {"invalid_source_url", "source_url_not_allowed"}:
                await self.repository.save(
                    SourceCapture(
                        mode=self.market.mode,
                        market_id=self.market.id,
                        venue=self.market.venue,
                        url=url,
                        retrieved_at=utcnow(),
                        status="failure",
                        error=code,
                    )
                )
            return None

    def finish(self, evidence):
        # Do not place capture times or failure IDs in semantic terms.
        details = dict(self.market.settlement_details)
        details["source_evidence"] = evidence
        details["source_references"] = sorted(self.documents, key=lambda r: r["url"])
        details["source_issues"] = sorted(set(self.issues))
        details["source_status"] = "incomplete" if self.issues else "captured"
        # Captured is a retrieval status, never semantic approval/completeness.
        return self.market.model_copy(
            update={
                "settlement_details": details,
                "raw": {**self.market.raw, "source_artifacts": self.references},
            }
        )
