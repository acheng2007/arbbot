from hashlib import sha256
from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, computed_field, model_validator

from arbbot.domain import Mode, Model, Venue, digest

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
Failure = Literal["timeout", "http_error", "network_error", "too_large", "invalid_content"]


class SourceCapture(Model):
    """A bounded retrieval result; failure codes never include credentials or raw errors."""

    mode: Mode
    market_id: str = Field(min_length=1, max_length=512)
    venue: Venue
    url: AnyHttpUrl
    retrieved_at: AwareDatetime
    content_type: str | None = Field(default=None, min_length=1, max_length=255)
    content: bytes | None = Field(default=None, max_length=MAX_DOCUMENT_BYTES)
    failure: Failure | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)

    @model_validator(mode="after")
    def validate_result(self):
        if self.url.username or self.url.password or self.url.query or self.url.fragment:
            raise ValueError("Source URLs must not contain credentials, queries, or fragments")
        if self.failure is None:
            if not self.content or not self.content_type:
                raise ValueError("Successful evidence requires content and its media type")
            if self.http_status is not None and not 200 <= self.http_status < 300:
                raise ValueError("Successful evidence requires a successful HTTP status")
        elif self.content is not None:
            raise ValueError("Failed retrievals must not retain partial evidence")
        return self

    @computed_field
    @property
    def content_digest(self) -> str | None:
        return sha256(self.content).hexdigest() if self.content is not None else None

    @property
    def artifact_id(self) -> str | None:
        if self.failure:
            return None
        return digest(
            [
                self.mode,
                self.market_id,
                self.venue,
                str(self.url),
                self.content_type,
                self.content_digest,
            ]
        )

    @property
    def capture_id(self) -> str:
        return digest(
            [
                self.mode,
                self.market_id,
                self.venue,
                str(self.url),
                self.retrieved_at.isoformat(),
                self.artifact_id,
                self.failure,
                self.http_status,
                self.content_type,
            ]
        )
