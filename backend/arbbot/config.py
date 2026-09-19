from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    max_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    slippage_bps: Decimal = Field(default=Decimal("10"), ge=0, le=10000)
    min_profit: Decimal = Field(default=Decimal("0.01"), gt=0)
    reviews_file: Path | None = None
    kalshi_tickers: list[str] = []
    polymarket_market_ids: list[str] = []
    kalshi_key_id: SecretStr | None = None
    kalshi_private_key_path: Path | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    sse_seconds: float = Field(default=2, ge=0.1, le=60)
