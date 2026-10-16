"""Direct Decisions API transport with shared attempt pacing and provider backoff."""

import asyncio
import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from arbbot.matching.classification_input import MAX_BYTES, serialized
from arbbot.matching.classification_models import Finding, Score

URL = "https://openrouter.ai/api/alpha/decisions"


class Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    choice: str
    confidence: Score
    probabilities: dict[str, Score]

    @model_validator(mode="after")
    def coherent(self):
        if self.type != "choice" or self.choice not in self.probabilities:
            raise ValueError("Invalid choice answer")
        if abs(sum(self.probabilities.values()) - 1) > 0.02:
            raise ValueError("Invalid probability distribution")
        if self.probabilities[self.choice] < max(self.probabilities.values()):
            raise ValueError("Choice is not the distribution winner")
        return self


class DecisionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str = Field(min_length=1, max_length=200)
    answers: dict[str, Choice]
    usage: dict = {}


def validate_response(data, request):
    value = DecisionsResponse.model_validate(data)
    if not value.model.startswith(request["model"]):
        raise ValueError("Unexpected model")
    if set(value.answers) != set(request["questions"]):
        raise ValueError("Unexpected question set")
    for key, answer in value.answers.items():
        if set(answer.probabilities) != set(request["questions"][key]["criteria"]):
            raise ValueError("Unexpected choices")
    return value


class ProviderFailure(Exception):
    def __init__(self, code, attempts, paused=False):
        super().__init__(code)
        self.code, self.attempts, self.paused = code, attempts, paused


class DecisionsProvider:
    def __init__(self, client, key, rate=2):
        self.client, self.key, self.rate = client, key, rate
        self.lock = asyncio.Lock()
        self.next_attempt = self.backoff_until = 0.0
        self.paused = False

    async def pace(self):
        async with self.lock:
            now = asyncio.get_running_loop().time()
            while (delay := max(self.next_attempt, self.backoff_until) - now) > 0:
                await asyncio.sleep(delay)
                now = asyncio.get_running_loop().time()
            if self.paused:
                raise ProviderFailure("provider_paused", 0, True)
            self.next_attempt = asyncio.get_running_loop().time() + 1 / self.rate

    def backoff(self, response, attempt):
        delay = 2**attempt
        if response is not None:
            raw = response.headers.get("Retry-After", "")
            try:
                delay = max(delay, float(raw))
            except ValueError:
                try:
                    delay = max(
                        delay, (parsedate_to_datetime(raw) - datetime.now(UTC)).total_seconds()
                    )
                except (ValueError, TypeError, OverflowError):
                    pass
        self.backoff_until = max(self.backoff_until, asyncio.get_running_loop().time() + delay)

    async def decide(self, request):
        if len(serialized(request)) > MAX_BYTES:
            raise ProviderFailure("input_too_large", 0)
        for attempt in range(1, 4):
            await self.pace()
            response = None
            try:
                async with asyncio.timeout(10):
                    response = await self.client.post(
                        URL,
                        content=serialized(request),
                        headers={
                            "Authorization": "Bearer " + self.key,
                            "Content-Type": "application/json",
                        },
                        timeout=10,
                    )
                if response.status_code in (400, 401, 403, 404, 422):
                    self.paused = True
                    raise ProviderFailure(f"provider_http_{response.status_code}", attempt, True)
                if response.status_code in (408, 429) or response.status_code >= 500:
                    self.backoff(response, attempt)
                    if attempt == 3:
                        raise ProviderFailure(f"provider_http_{response.status_code}", attempt)
                    continue
                response.raise_for_status()
                try:
                    if len(response.content) > 256 * 1024:
                        raise ValueError("Response too large")
                    return validate_response(response.json(), request), attempt
                except (ValueError, TypeError):
                    raise ProviderFailure("provider_invalid_response", attempt) from None
            except (httpx.TransportError, TimeoutError):
                self.backoff(None, attempt)
                if attempt == 3:
                    raise ProviderFailure("provider_transport_error", attempt) from None
            except httpx.HTTPStatusError:
                raise ProviderFailure(f"provider_http_{response.status_code}", attempt) from None
        raise AssertionError("unreachable")


class RecordedDecisions:
    """Exact recorded response replay. Unknown pairs fail closed without network fallback."""

    def __init__(self, path):
        self.path = Path(path)
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        if str(request.url) != URL or request.method != "POST":
            return httpx.Response(404)
        body = json.loads(request.content)
        pair = sorted(m["id"] for m in body["state"]["markets"])
        recording = json.loads(self.path.read_text())
        pair_key = "|".join(pair)
        entry = recording.get("pairs", {}).get(pair_key)
        if not entry:
            return httpx.Response(503)
        from arbbot.domain import digest

        expected = recording.get("request_hashes", {}).get(pair_key)
        if expected and digest(body) != expected:
            return httpx.Response(422)
        status = recording.get("status", 200)
        return httpx.Response(status, json=entry, headers={"Retry-After": "1"})


def finding(answer, evidence_ids=()):
    return Finding(
        choice=answer.choice,
        confidence=answer.confidence,
        probabilities=answer.probabilities,
        evidence_ids=evidence_ids,
    )
