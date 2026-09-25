from decimal import Decimal

import pytest
from pydantic import ValidationError

from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.domain import Scenario, utcnow
from arbbot.matching.service import match_markets
from tests.test_contracts import live_pair


@pytest.mark.parametrize("yes,no", [("0", "0"), ("0.5", "0"), ("1", "1"), ("0.25", "0.5")])
def test_noncomplementary_or_variable_refund_is_not_supported(yes, no):
    with pytest.raises(ValidationError, match="Non-complementary"):
        Scenario(name="refund", left_yes=yes, left_no=no, right_yes="0", right_no="1")


def test_partial_explicit_payouts_are_rejected():
    with pytest.raises(ValidationError, match="both venues"):
        Scenario(name="partial", left_yes="0", right_yes="0", left_no="1")


@pytest.mark.parametrize("fraction", ["0", "0.25", "0.5", "1"])
def test_fixed_complementary_payouts_are_exact(fraction):
    value = Decimal(fraction)
    scenario = Scenario(
        name="fixed settlement",
        left_yes=value,
        right_yes=value,
        left_no=1 - value,
        right_no=1 - value,
    )
    for venue in ("left", "right"):
        assert scenario.payout(venue, "yes") == value
        assert scenario.payout(venue, "no") == 1 - value
    assert isinstance(scenario.model_dump(mode="json")["left_no"], str)


async def test_legacy_review_cannot_authorize_live_matching_or_evaluation(fixture_market):
    markets, books, review, definitions = live_pair(fixture_market)
    verified = match_markets(markets, [review], definitions)[0]
    assert evaluate(verified, *markets, books, Settings(_env_file=None), utcnow()).opportunities
    legacy = review.model_copy(
        update={
            "scenarios": tuple(
                s.model_copy(update={"left_no": None, "right_no": None}) for s in review.scenarios
            )
        }
    )
    match = match_markets(markets, [legacy], definitions)[0]
    assert match.status == "candidate"
    # A previously persisted verified match must also fail at evaluation time.
    result = evaluate(
        verified.model_copy(update={"review": legacy}),
        *markets,
        books,
        Settings(_env_file=None),
        utcnow(),
    )
    assert not result.opportunities
    assert any(
        "explicit_settlement_payouts_required" in reason for reason in result.blocked_reasons
    )


async def test_divergent_exception_leaves_both_purchased_legs_losing(fixture_market):
    markets, books, review, definitions = live_pair(fixture_market)
    reviewed = review.model_copy(
        update={
            "scenarios": (
                *review.scenarios,
                Scenario(
                    name="divergent fallback",
                    left_yes="0",
                    left_no="1",
                    right_yes="1",
                    right_no="0",
                ),
            )
        }
    )
    match = match_markets(markets, [reviewed], definitions)[0]
    assert not evaluate(match, *markets, books, Settings(_env_file=None), utcnow()).opportunities
