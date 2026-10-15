from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from arbbot.discovery.models import DEFAULT_FAMILIES, EventFamily
from arbbot.domain import Venue
from arbbot.sources.models import MAX_CONTENT_BYTES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARBBOT_", env_file=".env", extra="ignore")

    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY"
    )
    automatic_qualification: bool = True
    classification_enabled: bool = True
    classification_model: Literal["typesafe/jev-1.13"] = "typesafe/jev-1.13"
    classification_requests_per_second: float = Field(default=2, gt=0, le=2)
    classification_probability: float = Field(default=0.80, ge=0, le=1)
    classification_confidence: float = Field(default=0.80, ge=0, le=1)
    classification_recording_file: Path | None = None

    database_url: SecretStr = SecretStr("postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot")
    mode: Literal["simulation", "live"] = "simulation"
    poll_seconds: float = Field(default=5, ge=1, le=3600)
    fee_refresh_seconds: float = Field(default=120, ge=10, le=300)
    max_quote_age_seconds: int = Field(default=30, ge=1, le=300)
    max_quote_skew_seconds: int = Field(default=10, ge=0, le=60)
    health_timeout_seconds: int = Field(default=120, ge=10)
    discovery_limit: int = Field(default=50, ge=1, le=1000)
    monitoring_limits: dict[Venue, Annotated[int, Field(ge=1, le=1000)]] = {}
    discovery_families: tuple[EventFamily, ...] = Field(
        default=DEFAULT_FAMILIES, min_length=1, max_length=8
    )
    discovery_mode: Literal["focused", "broad"] = "focused"
    catalog_page_size: int = Field(default=100, ge=1, le=100)
    discovery_scan_pages: int = Field(default=8, ge=1, le=50)
    catalog_refresh_seconds: float = Field(default=300, ge=10, le=3600)
    catalog_max_age_seconds: int = Field(default=900, ge=30, le=86400)
    catalog_timeout_seconds: float = Field(default=120, ge=1, le=600)
    max_contracts: int = Field(default=1000, ge=1, le=10000)
    source_max_bytes: int = Field(default=1_000_000, ge=1024, le=MAX_CONTENT_BYTES)
    max_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    slippage_bps: Decimal = Field(default=Decimal("10"), ge=0, le=10000)
    min_profit: Decimal = Field(default=Decimal("0.01"), gt=0)
    recording_file: Path | None = None
    definitions_file: Path | None = None
    reviews_file: Path | None = None
    review_source: Literal["database", "files"] = "database"
    kalshi_tickers: list[str] = []
    polymarket_market_ids: list[str] = []
    polymarket_us_market_ids: list[str] = []
    enabled_venues: tuple[Venue, ...] = Field(default=("kalshi", "polymarket"), min_length=1)
    polymarket_websocket: bool = True
    kalshi_key_id: SecretStr | None = None
    kalshi_private_key_path: Path | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    sse_seconds: float = Field(default=2, ge=0.1, le=60)
    auth_issuer: str | None = None
    auth_audience: str | None = Field(default=None, min_length=1, max_length=512)
    auth_jwks_url: str | None = None
    auth_jwks_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    auth_refresh_seconds: int = Field(default=30, ge=1, le=300)
    auth_clock_skew_seconds: int = Field(default=0, ge=0, le=30)
    auth_max_token_seconds: int = Field(default=900, ge=60, le=3600)

    def monitoring_limit(self, venue):
        return self.monitoring_limits.get(venue, self.discovery_limit)

    @model_validator(mode="after")
    def validate_catalog(self):
        if self.mode == "live":
            if "discovery_mode" not in self.model_fields_set:
                self.discovery_mode = "broad"
            if "enabled_venues" not in self.model_fields_set:
                self.enabled_venues = ("kalshi", "polymarket_us")
        if self.recording_file and (
            self.mode != "live"
            or any(venue not in ("kalshi", "polymarket_us") for venue in self.enabled_venues)
        ):
            raise ValueError("Recorded exchange replay requires the public Kalshi/US adapter path")
        if self.recording_file and (self.kalshi_key_id or self.kalshi_private_key_path):
            raise ValueError("Offline recording mode cannot use private exchange credentials")
        from arbbot.venues import VENUES

        if any(venue not in VENUES for venue in self.enabled_venues):
            raise ValueError("Enabled venues must be registered")
        if len(set(self.enabled_venues)) != len(self.enabled_venues):
            raise ValueError("Enabled venues must be unique")
        if (
            self.catalog_max_age_seconds
            <= self.catalog_refresh_seconds + self.catalog_timeout_seconds
        ):
            raise ValueError("Catalog age limit must exceed refresh interval plus refresh timeout")
        if len({family.name for family in self.discovery_families}) != len(self.discovery_families):
            raise ValueError("Discovery family names must be unique")
        return self

    @model_validator(mode="after")
    def validate_auth(self):
        configured = (self.auth_issuer, self.auth_audience, self.auth_jwks_url)
        if any(v is not None for v in configured) and not all(configured):
            raise ValueError("Configure issuer, audience and JWKS URL together")
        for value in (self.auth_issuer, self.auth_jwks_url):
            if value:
                url = urlsplit(value)
                if (
                    url.scheme != "https"
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError(
                        "Identity URLs require HTTPS without credentials/query/fragment"
                    )
        if "*" in self.cors_origins or "null" in self.cors_origins:
            raise ValueError("CORS requires explicit trusted origins")
        if self.auth_refresh_seconds > self.auth_jwks_ttl_seconds:
            raise ValueError("Auth refresh cooldown must not exceed key cache TTL")
        return self

    tracing_enabled: bool = False
    tracing_endpoint: str = "http://localhost:4318/v1/traces"
    tracing_headers: dict[str, SecretStr] = {}
    tracing_sample_ratio: float = Field(default=0.1, ge=0, le=1)
    tracing_export_timeout_seconds: float = Field(default=2, gt=0, le=10)
    tracing_queue_size: int = Field(default=512, ge=64, le=8192)

    @field_validator("tracing_endpoint")
    @classmethod
    def validate_tracing_endpoint(cls, value):
        url = urlsplit(value)
        if (
            not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or not (
                url.scheme == "https"
                or (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1"))
            )
        ):
            raise ValueError("Tracing requires HTTPS or loopback HTTP, without URL credentials")
        return value
