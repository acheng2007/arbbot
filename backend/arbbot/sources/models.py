"""Settlement source evidence contracts.

An artifact records one retrieval attempt for one document that a settlement
review depends on. Captured content is immutable: a changed document produces a
new artifact instead of overwriting the previous one. Failed retrievals are
recorded with the same provenance so missing evidence stays visible instead of
silently disappearing from a review.
"""

import hashlib
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AwareDatetime, ConfigDict, Field, field_validator

from arbbot.domain import Mode, Model, Venue, digest

# Absolute ceiling for one stored document. Deployments may configure a lower
# limit, but nothing may persist a larger document.
MAX_CONTENT_BYTES = 5_000_000

FailureReason = Literal[
    "http_error",
    "timeout",
    "network_error",
    "too_large",
    "unsupported_content",
    "invalid_document",
]

Url = Annotated[str, Field(min_length=8, max_length=2048)]
Label = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_.-]*$")]
MediaType = Annotated[str, Field(min_length=3, max_length=255)]


def content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class SourceModel(Model):
    # Binary documents must survive JSON transport without lossy decoding.
    model_config = ConfigDict(
        extra="forbid", frozen=True, ser_json_bytes="base64", val_json_bytes="base64"
    )

    @field_validator("url", check_fields=False)
    @classmethod
    def absolute_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source URL must be an absolute http or https URL")
        return value


class SourceReference(SourceModel):
    """Identity of the evidence a review depends on, independent of the outcome."""

    venue: Venue
    mode: Mode
    market_id: str = Field(min_length=1)
    url: Url
    # Names the evidence role, such as kalshi_series or resolution_source.
    label: Label


class SourceCapture(SourceReference):
    """A document retrieved successfully."""

    content: Annotated[bytes, Field(max_length=MAX_CONTENT_BYTES)]
    content_type: MediaType
    retrieved_at: AwareDatetime
    # Timestamp declared by the source, kept separate from the receipt time.
    source_at: AwareDatetime | None = None
    details: dict = {}

    @property
    def digest(self) -> str:
        return content_digest(self.content)

    @property
    def observed_at(self) -> datetime:
        return self.retrieved_at

    @property
    def id(self) -> str:
        return digest(["captured", self.mode, self.market_id, self.url, self.label, self.digest])


class SourceFailure(SourceReference):
    """A retrieval that produced no trustworthy document."""

    reason: FailureReason
    detail: str = Field(min_length=1, max_length=2048)
    status_code: int | None = Field(default=None, ge=100, le=599)
    attempted_at: AwareDatetime
    details: dict = {}

    @property
    def observed_at(self) -> datetime:
        return self.attempted_at

    @property
    def id(self) -> str:
        return digest(
            [
                "failed",
                self.mode,
                self.market_id,
                self.url,
                self.label,
                self.reason,
                self.status_code,
                self.detail,
            ]
        )


class SourceArtifactSummary(SourceModel):
    """Metadata for a persisted retrieval attempt, without the document bytes."""

    id: str
    venue: Venue
    mode: Mode
    market_id: str
    url: Url
    label: Label
    status: Literal["captured", "failed"]
    content_type: MediaType | None = None
    content_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=0)
    source_at: AwareDatetime | None = None
    reason: FailureReason | None = None
    detail: str | None = None
    status_code: int | None = None
    # Terms the market carried when this evidence was captured, so later terms
    # changes can invalidate reviews that relied on it.
    market_terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    first_seen_at: AwareDatetime
    last_seen_at: AwareDatetime
    observations: int = Field(ge=1)
    details: dict = {}

    @property
    def complete(self) -> bool:
        return self.status == "captured"


class SourceArtifact(SourceArtifactSummary):
    """A persisted retrieval attempt including the original document bytes."""

    content: bytes | None = None


def bounded_capture(
    *,
    content: bytes,
    limit: int = MAX_CONTENT_BYTES,
    **fields,
) -> SourceCapture | SourceFailure:
    """Build a capture, or an explicit failure when the document is too large.

    Fetchers use this so an oversized document is recorded as missing evidence
    rather than silently truncated or dropped.
    """
    if not 0 < limit <= MAX_CONTENT_BYTES:
        raise ValueError(f"Document limit must be between 1 and {MAX_CONTENT_BYTES} bytes")
    if len(content) > limit:
        retrieved_at = fields.pop("retrieved_at")
        fields.pop("content_type", None)
        fields.pop("source_at", None)
        return SourceFailure(
            reason="too_large",
            detail=f"Document of {len(content)} bytes exceeds the {limit} byte limit",
            attempted_at=retrieved_at,
            **fields,
        )
    return SourceCapture(content=content, **fields)
