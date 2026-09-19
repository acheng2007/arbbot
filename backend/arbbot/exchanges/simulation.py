from datetime import UTC, datetime, timedelta
from decimal import Decimal

from arbbot.domain import Book, CostPolicy, Level, Market, Review, Scenario, utcnow

CLOSE = datetime(2099, 1, 1, tzinfo=UTC)


class SimulationAdapter:
    def __init__(self, venue: str):
        self.venue = venue

    async def discover(self, limit: int) -> list[Market]:
        return [
            Market(
                id=f"{self.venue}:SIM-DEMO",
                external_id="SIM-DEMO",
                venue=self.venue,
                mode="simulation",
                title="SIMULATION: Will the demo index finish above 100?",
                rules=(
                    "Synthetic binary event; YES and NO are complementary, including cancellation."
                ),
                closes_at=CLOSE,
                status="open",
                settlement_asset="USD",
                raw={"synthetic": True},
                observed_at=utcnow(),
            )
        ]

    async def fetch_book(self, market: Market) -> Book:
        yes, no = ("0.40", "0.63") if self.venue == "kalshi" else ("0.58", "0.45")
        now = utcnow()
        return Book(
            market_id=market.id,
            mode="simulation",
            yes_asks=(Level(price=yes, size="20"), Level(price="0.80", size="100")),
            no_asks=(Level(price=no, size="15"), Level(price="0.85", size="100")),
            received_at=now,
            source_at=now,
            raw={"synthetic": True},
        )


def simulation_reviews(markets: list[Market]) -> list[Review]:
    indexed = {m.venue: m for m in markets if m.mode == "simulation"}
    if set(indexed) != {"kalshi", "polymarket"}:
        return []
    a, b = indexed["kalshi"], indexed["polymarket"]
    policy = CostPolicy(
        fee_per_contract=Decimal("0.02"),
        fixed_fee=Decimal("0.01"),
        min_order_size=Decimal(1),
        min_notional=Decimal(0),
        cost_fx=Decimal(1),
        payout_fx=Decimal(1),
        evidence="Synthetic test fee bounds only.",
    )
    return [
        Review(
            left_id=a.id,
            right_id=b.id,
            left_terms_hash=a.terms_hash,
            right_terms_hash=b.terms_hash,
            status="verified",
            reviewer="simulation-fixture",
            rationale="Synthetic equivalent contracts.",
            resolution_sources="Shared synthetic resolution source.",
            deadlines_and_timezones="Same synthetic UTC deadline.",
            cancellation_and_exceptions="Synthetic cancellation pays half on each outcome.",
            expires_at=utcnow() + timedelta(days=1),
            left_costs=policy,
            right_costs=policy,
            scenarios=(
                Scenario(name="yes", left_yes="1", right_yes="1"),
                Scenario(name="no", left_yes="0", right_yes="0"),
                Scenario(name="cancelled", left_yes="0.5", right_yes="0.5"),
            ),
        )
    ]
