"""Stable exchange identities and adapter construction."""

from dataclasses import dataclass

from arbbot.domain import Model, Venue
from arbbot.qualification.providers import Capabilities, PublicEvidence


class VenueInfo(Model):
    id: Venue
    name: str
    enabled: bool
    evaluation_enabled: bool
    access_note: str


def kalshi(client, settings, once):
    from arbbot.exchanges.base import ExchangeHTTP
    from arbbot.exchanges.kalshi import KalshiAdapter

    return KalshiAdapter(ExchangeHTTP(client), settings)


def international(client, settings, once):
    from arbbot.exchanges.base import ExchangeHTTP
    from arbbot.exchanges.polymarket import PolymarketAdapter
    from arbbot.streams.polymarket import StreamingPolymarketAdapter

    adapter = (
        StreamingPolymarketAdapter
        if settings.polymarket_websocket and not once
        else PolymarketAdapter
    )
    return adapter(ExchangeHTTP(client), settings.polymarket_market_ids)


def polymarket_us(client, settings, once):
    from arbbot.exchanges.base import ExchangeHTTP
    from arbbot.exchanges.polymarket_us import PolymarketUSAdapter

    return PolymarketUSAdapter(ExchangeHTTP(client), settings.polymarket_us_market_ids)


@dataclass(frozen=True)
class Registration:
    name: str
    factory: object
    evaluation: bool
    access_note: str
    capabilities: Capabilities | None = None


VENUES = {
    "kalshi": Registration(
        "Kalshi",
        kalshi,
        True,
        "Account and product eligibility are unverified",
        Capabilities(
            PublicEvidence(
                (
                    "kalshi.com",
                    "www.kalshi.com",
                    "external-api.kalshi.com",
                    "assets.kalshi.com",
                    "kalshi-public-docs.s3.amazonaws.com",
                    "kalshi-public-docs.s3.us-east-1.amazonaws.com",
                    "www.bls.gov",
                    "bls.gov",
                    "www.federalreserve.gov",
                )
            ),
            "direct",
        ),
    ),
    "polymarket": Registration(
        "Polymarket International",
        international,
        True,
        "International research feed; not a US trading route",
        Capabilities(PublicEvidence(("polymarket.com", "gamma-api.polymarket.com"))),
    ),
    "polymarket_us": Registration(
        "Polymarket US",
        polymarket_us,
        True,
        "Public conditional estimates; account eligibility and balances are unverified",
        Capabilities(
            PublicEvidence(("polymarketexchange.com", "gateway.polymarket.us")), "standard", True
        ),
    ),
}


def venue_info(settings):
    return [
        VenueInfo(
            id=key,
            name=value.name,
            enabled=key in settings.enabled_venues,
            evaluation_enabled=value.evaluation and key in settings.enabled_venues,
            access_note=value.access_note,
        )
        for key, value in VENUES.items()
    ]


def build_adapters(client, settings, once=False):
    from arbbot.exchanges.simulation import SimulationAdapter

    return [
        SimulationAdapter(venue)
        if settings.mode == "simulation"
        else VENUES[venue].factory(client, settings, once)
        for venue in settings.enabled_venues
    ]
