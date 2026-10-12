"""Bounded evidence reads. No redirects, arbitrary hosts, cookies or credentials."""

import asyncio
import json
from collections import OrderedDict
from time import monotonic

import httpx

from arbbot.domain import utcnow
from arbbot.sources.models import MAX_CONTENT_BYTES, SourceCapture, SourceFailure
from arbbot.sources.text import derive_text

ALLOWED_HOSTS = frozenset(
    {
        "external-api.kalshi.com",
        "docs.kalshi.com",
        "docs.polymarket.us",
        "gamma-api.polymarket.com",
        "gateway.polymarket.us",
        "polymarketexchange.com",
        "www.polymarketexchange.com",
        "assets.kalshi.com",
        "kalshi-public-docs.s3.amazonaws.com",
        "kalshi-public-docs.s3.us-east-1.amazonaws.com",
        "www.bls.gov",
        "bls.gov",
        "www.federalreserve.gov",
    }
)
CONTENT_TYPES = {"application/json", "application/pdf", "text/plain", "text/html"}


class EvidenceError(ValueError):
    pass


class SourceFetcher:
    def __init__(self, *, transport=None, ttl=300, max_bytes=1_000_000):
        if not 0 < max_bytes <= MAX_CONTENT_BYTES:
            raise ValueError("Invalid source byte limit")
        self.transport, self.ttl = transport, ttl
        self.max_bytes = max_bytes
        self.cache = OrderedDict()
        self.resolved_urls = {}
        self.locks = [asyncio.Lock() for _ in range(16)]
        self.capacity = asyncio.Semaphore(4)

    async def read(self, url):
        if not isinstance(url, str) or len(url) > 2048:
            raise EvidenceError("invalid_source_url")
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
        async with asyncio.timeout(20), self.locks[hash(url) % len(self.locks)]:
            cached = self.cache.get(url)
            if cached and monotonic() - cached[0] < self.ttl:
                return cached[1:]
            async with self.capacity:
                async with httpx.AsyncClient(
                    timeout=5, follow_redirects=False, trust_env=False, transport=self.transport
                ) as client:
                    current_url = url
                    redirects = 0
                    for attempt in range(6):
                        try:
                            async with client.stream("GET", current_url) as response:
                                if (
                                    response.status_code in {301, 302, 307, 308}
                                    and parsed.host
                                    in {"polymarketexchange.com", "www.polymarketexchange.com"}
                                    and parsed.path.startswith("/files/legal/latest/")
                                ):
                                    target = httpx.URL(current_url).join(
                                        response.headers.get("location", "")
                                    )
                                    if (
                                        redirects >= 3
                                        or target.scheme != "https"
                                        or target.host != parsed.host
                                        or target.port not in (None, 443)
                                        or target.userinfo
                                        or target.query
                                        or target.fragment
                                        or not target.path.startswith("/files/legal/")
                                    ):
                                        raise EvidenceError("source_redirect_not_allowed")
                                    redirects += 1
                                    current_url = str(target)
                                    continue
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
                                    if len(data) + len(chunk) > self.max_bytes:
                                        raise EvidenceError("response_too_large")
                                    data.extend(chunk)
                                if not data:
                                    raise EvidenceError("empty_source")
                                result = (bytes(data), content_type, utcnow())
                                self.resolved_urls[url] = current_url
                                self.cache[url] = (monotonic(), *result)
                                self.cache.move_to_end(url)
                                while len(self.cache) > 128:
                                    evicted, _ = self.cache.popitem(last=False)
                                    self.resolved_urls.pop(evicted, None)
                                return result
                        except httpx.RequestError:
                            if attempt >= 2:
                                raise EvidenceError("source_transport_failure") from None
                            await asyncio.sleep(0.1 * 2**attempt)


class EvidenceCollector:
    def __init__(self, market, repository, fetcher):
        self.market, self.repository, self.fetcher = market, repository, fetcher
        self.references, self.issues = [], []
        self.documents = []
        self.texts = {}
        self.text_provenance = []

    async def get(self, url, *, label="resolution_source", json_document=False):
        try:
            content, content_type, retrieved_at = await self.fetcher.read(url)
            capture = SourceCapture(
                mode=self.market.mode,
                market_id=self.market.id,
                venue=self.market.venue,
                url=url,
                label=label,
                retrieved_at=retrieved_at,
                content=content,
                content_type=content_type,
                details={"canonical_url": getattr(self.fetcher, "resolved_urls", {}).get(url, url)},
            )
            saved = await self.repository.record(capture)
            self.references.append(
                {"id": saved.id, "url": saved.url, "label": label, "digest": saved.content_digest}
            )
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
            if content_type == "application/pdf" and (
                not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]
            ):
                raise EvidenceError("malformed_pdf")
            derived = await derive_text(content, content_type, saved.id)
            self.text_provenance.append(
                {
                    "artifact_id": saved.id,
                    "label": label,
                    "url": str(saved.url),
                    "content_digest": saved.content_digest,
                    "extractor_version": derived.extractor_version,
                    "text_digest": derived.text_digest,
                    "status": derived.status,
                }
            )
            if derived.status != "complete":
                self.issues.append("source_text_" + (derived.reason or "unavailable"))
            if derived.pages:
                key = "source_text_" + label
                text = "\n".join(
                    (f"Page {p.page}:\n" if p.page else "") + p.text for p in derived.pages
                )
                self.texts[key] = (self.texts.get(key, "") + "\n" + text).strip()
            return content
        except (EvidenceError, TimeoutError) as exc:
            code = str(exc) if isinstance(exc, EvidenceError) else "source_timeout"
            self.issues.append(code)
            # Invalid/credentialed URLs are never persisted or echoed in errors.
            if code not in {"invalid_source_url", "source_url_not_allowed"}:
                reason = (
                    "timeout"
                    if code == "source_timeout"
                    else "too_large"
                    if code == "response_too_large"
                    else "unsupported_content"
                    if code == "unsupported_content_type"
                    else "http_error"
                    if code.startswith("source_http_")
                    else "network_error"
                    if code == "source_transport_failure"
                    else "invalid_document"
                )
                await self.repository.record(
                    SourceFailure(
                        mode=self.market.mode,
                        market_id=self.market.id,
                        venue=self.market.venue,
                        url=url,
                        label=label,
                        attempted_at=utcnow(),
                        reason=reason,
                        detail=code,
                        status_code=int(code.removeprefix("source_http_"))
                        if code.startswith("source_http_")
                        else None,
                    )
                )
            return None

    def finish(self, evidence):
        # Do not place capture times or failure IDs in semantic terms.
        details = dict(self.market.settlement_details)
        details.update(self.texts)
        details["source_text_provenance"] = sorted(
            self.text_provenance, key=lambda item: (item["label"], item["artifact_id"])
        )
        details["source_evidence"] = evidence
        # Quotations can reference these stable, top-level strings. The original
        # complete response stays in the immutable artifact, outside semantic terms.
        details["source_evidence_text"] = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
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
