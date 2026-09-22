from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from arbbot.arbitrage.engine import evaluate, fill
from arbbot.config import Settings
from arbbot.domain import Level, Scenario, utcnow
from arbbot.matching.service import match_markets


def calculate(fixture, **options):
    markets, books, _, match = fixture
    return evaluate(match, *markets, books, Settings(_env_file=None, **options), utcnow())


async def test_depth_fees_and_worst_case_payoff(fixture_market):
    result = calculate(fixture_market)
    assert len(result.opportunities) == 1
    opportunity = result.opportunities[0]
    assert opportunity.quantity == Decimal("15")
    assert opportunity.capital_required == Decimal("13.39")
    assert opportunity.fee_bound == Decimal("0.62")
    assert opportunity.slippage_reserve == Decimal("0.02")
    assert opportunity.net_profit == Decimal("1.61")
    assert set(opportunity.scenario_payouts.values()) == {Decimal("15")}
    assert opportunity.classification == "simulation"
    assert isinstance(opportunity.model_dump(mode="json")["net_profit"], str)


async def test_capital_bound_sizes_down(fixture_market):
    result = calculate(fixture_market, max_capital=Decimal("5"))
    assert result.opportunities[0].quantity == 5
    assert result.opportunities[0].capital_required <= 5


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"received_at": -timedelta(minutes=2), "source_at": None}, "book_stale"),
        ({"source_at": timedelta(seconds=10)}, "book_from_future"),
        ({"mode": "live"}, "book_mode_mismatch"),
    ],
)
async def test_bad_quotes_block_evaluation(fixture_market, change, expected):
    markets, books, _, match = fixture_market
    now = utcnow()
    change = {
        key: now + value if isinstance(value, timedelta) else value for key, value in change.items()
    }
    books[markets[0].id] = books[markets[0].id].model_copy(update=change)
    result = evaluate(match, *markets, books, Settings(_env_file=None), now)
    assert not result.opportunities
    assert any(expected in reason for reason in result.blocked_reasons)


async def test_cross_venue_skew(fixture_market):
    markets, books, _, _ = fixture_market
    books[markets[0].id] = books[markets[0].id].model_copy(
        update={"source_at": utcnow() - timedelta(seconds=15)}
    )
    assert calculate(fixture_market).blocked_reasons == ("quotes_not_synchronized",)


async def test_missing_liquidity_and_minimum_order(fixture_market):
    markets, books, _, _ = fixture_market
    books[markets[1].id] = books[markets[1].id].model_copy(
        update={"min_order_size": Decimal("200")}
    )
    assert not calculate(fixture_market).opportunities


async def test_expensive_exception_blocks_apparent_arbitrage(fixture_market):
    markets, books, review, match = fixture_market
    review = review.model_copy(
        update={
            "scenarios": (
                *review.scenarios,
                Scenario(name="divergent_resolution", left_yes="0", right_yes="1"),
            )
        }
    )
    match = match.model_copy(update={"review": review})
    result = evaluate(match, *markets, books, Settings(_env_file=None), utcnow())
    assert not result.opportunities


async def test_unreviewed_and_changed_terms_never_auto_verify(fixture_market):
    markets, books, review, _ = fixture_market
    candidate = match_markets(markets, [])[0]
    assert candidate.status == "candidate"
    assert not evaluate(
        candidate, *markets, books, Settings(_env_file=None), utcnow()
    ).opportunities
    markets[0] = markets[0].model_copy(update={"rules": "Materially changed resolution terms"})
    changed = match_markets(markets, [review])[0]
    assert changed.status == "candidate"
    assert "changed" in changed.reason


async def test_expired_and_rejected_reviews(fixture_market):
    markets, _, review, _ = fixture_market
    expired = review.model_copy(update={"expires_at": utcnow() - timedelta(seconds=1)})
    assert match_markets(markets, [expired])[0].status == "candidate"
    rejected = review.model_copy(update={"status": "rejected"})
    assert match_markets(markets, [rejected])[0].status == "rejected"


async def test_closed_market_is_blocked(fixture_market):
    fixture_market[0][0] = fixture_market[0][0].model_copy(update={"status": "closed"})
    assert not calculate(fixture_market).opportunities


def test_fractional_depth_consumption_is_exact():
    levels = (Level(price="0.10", size="0.3"), Level(price="0.20", size="0.7"))
    assert fill(levels, Decimal(1)) == (Decimal("0.17"), Decimal("0.20"))
    assert fill(levels, Decimal(2)) is None


@pytest.mark.parametrize("price,size", [("NaN", "1"), ("1.1", "1"), ("0.5", "0"), ("-1", "1")])
def test_invalid_levels_rejected(price, size):
    with pytest.raises(ValidationError):
        Level(price=price, size=size)
