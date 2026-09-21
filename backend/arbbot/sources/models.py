"""Validated source captures for future venue-specific evidence fetchers."""

from hashlib import sha256
from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, model_validator

from arbbot.domain import Mode, Model, Venue, digest

MAX_CONTENT_BYTES = 2 * 1024 * 1024


class SourceCapture(Model):
    mode: Mode
    market_id: str = Field(min_length=1, max_length=512)
    venue: Venue
    url: AnyHttpUrl = Field(max_length=4096)
    retrieved_at: AwareDatetime
    status: Literal["success", "failure"]
    content: bytes | None = Field(default=None, max_length=MAX_CONTENT_BYTES)
    content_type: str | None = Field(default=None, min_length=1, max_length=255)
    error: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_capture(self):
        if self.url.username or self.url.password:
            raise ValueError("Source URLs must not contain credentials")
        if self.status == "success":
            if not self.content or not self.content_type or self.error is not None:
                raise ValueError("Success requires nonempty content, content type and no error")
        elif self.content is not None or self.content_type is not None or not self.error:
            raise ValueError("Failure requires an error and no content or content type")
        return self

    @property
    def content_digest(self) -> str | None:
        return sha256(self.content).hexdigest() if self.content is not None else None

    @property
    def id(self) -> str:
        # Successful recaptures preserve the first stored capture time; failed
        # attempts retain their timestamps so an outage remains auditable.
        return digest(
            [
                self.mode,
                self.market_id,
                self.venue,
                str(self.url),
                self.status,
                self.content_digest,
                self.content_type,
                self.error,
                self.retrieved_at.isoformat() if self.status == "failure" else None,
            ]
        )
