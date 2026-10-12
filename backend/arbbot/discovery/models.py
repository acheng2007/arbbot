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
    EventFamily(
        name="us_fed_rate_hike",
        kalshi_series=("KXFEDHIKE",),
        polymarket_queries=("Fed rate hike",),
        keywords=("Fed rate hike", "Federal Reserve hike"),
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
    discovery_mode: Literal["focused", "broad"] = "focused"
    query_scope: str | None = None
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
    catalog_market_count: int = Field(default=0, ge=0)
    monitoring_limit: int | None = Field(default=None, ge=1)
    continuation: str | int | None = None
    coverage_complete: bool = False
    missing_source_market_ids: tuple[str, ...] = ()
    error: str | None = None


class CatalogObservation(Model):
    venue: Venue
    external_id: str
    observation_id: str
    market_id: str | None
    supported: bool
    reason: str
    observed_at: AwareDatetime
    raw: dict
