from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from arbbot.domain import Market, Mode, Model, Venue

SearchTerm = Annotated[str, Field(min_length=1, max_length=100)]


class EventFamily(Model):
    name: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    kalshi_series: tuple[SearchTerm, ...] = Field(min_length=1, max_length=8)
    polymarket_queries: tuple[SearchTerm, ...] = Field(min_length=1, max_length=8)
    keywords: tuple[SearchTerm, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def nonblank(self):
        if any(
            not term.strip()
            for term in (*self.kalshi_series, *self.polymarket_queries, *self.keywords)
        ):
            raise ValueError("Discovery terms must not be blank")
        return self


DEFAULT_FAMILIES = (
    EventFamily(
        name="us_cpi",
        kalshi_series=("KXCPI", "KXCPIYOY"),
        polymarket_queries=("US inflation", "CPI"),
        keywords=("inflation", "CPI", "Consumer Price Index"),
    ),
)


class DiscoveryDecision(Model):
    external_id: str
    family: str
    included: bool
    reason: str


class DiscoveryScan(Model):
    markets: tuple[Market, ...]
    decisions: tuple[DiscoveryDecision, ...]
    pages_scanned: int = Field(ge=0)
    truncated: bool


class CatalogReport(Model):
    mode: Mode
    venue: Venue
    status: Literal["ready", "degraded", "failed", "stale"]
    started_at: AwareDatetime
    completed_at: AwareDatetime
    valid_until: AwareDatetime
    selected_market_ids: tuple[str, ...]
    decisions: tuple[DiscoveryDecision, ...]
    pages_scanned: int = Field(ge=0)
    truncated: bool
    missing_source_market_ids: tuple[str, ...] = ()
    error: str | None = None
