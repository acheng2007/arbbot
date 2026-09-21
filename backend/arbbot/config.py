from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from arbbot.sources.models import MAX_CONTENT_BYTES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARBBOT_", env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot")
    mode: Literal["simulation", "live"] = "simulation"
    poll_seconds: float = Field(default=5, ge=1, le=3600)
    max_quote_age_seconds: int = Field(default=30, ge=1, le=300)
    max_quote_skew_seconds: int = Field(default=10, ge=0, le=60)
    health_timeout_seconds: int = Field(default=120, ge=10)
    discovery_limit: int = Field(default=50, ge=1, le=1000)
    max_contracts: int = Field(default=1000, ge=1, le=10000)
    source_max_bytes: int = Field(default=1_000_000, ge=1024, le=MAX_CONTENT_BYTES)
    max_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    slippage_bps: Decimal = Field(default=Decimal("10"), ge=0, le=10000)
    min_profit: Decimal = Field(default=Decimal("0.01"), gt=0)
    definitions_file: Path | None = None
    reviews_file: Path | None = None
    kalshi_tickers: list[str] = []
    polymarket_market_ids: list[str] = []
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
