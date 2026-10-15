from decimal import Decimal

import pytest
from pydantic import ValidationError

from arbbot.arbitrage.engine import evaluate
from arbbot.config import Settings
from arbbot.domain import Scenario, utcnow
from arbbot.matching.contracts import evidence_issues
from arbbot.matching.service import match_markets
from arbbot.matching.settlement import settlement_issues
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


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_policy",
        "unknown_policy",
        "missing_mapping",
        "wrong_payout",
        "missing_scenario",
        "unknown_condition",
        "duplicate_mapping",
    ],
)
async def test_known_exception_conditions_must_be_covered(fixture_market, mutation):
    markets, books, review, definitions = live_pair(fixture_market)
    assert not settlement_issues(review, *definitions)
    if mutation == "missing_policy":
        definitions[0] = definitions[0].model_copy(update={"settlement_policies": None})
    elif mutation == "unknown_policy":
        policies = list(definitions[0].settlement_policies)
        policies[1] = policies[1].model_copy(update={"status": "unknown"})
        definitions[0] = definitions[0].model_copy(update={"settlement_policies": tuple(policies)})
    else:
        mappings = list(review.settlement_mappings)
        if mutation == "missing_mapping":
            mappings.pop()
        elif mutation == "wrong_payout":
            mappings[0] = mappings[0].model_copy(update={"scenarios": ("yes",)})
        elif mutation == "missing_scenario":
            mappings[0] = mappings[0].model_copy(update={"scenarios": ("absent",)})
        elif mutation == "unknown_condition":
            mappings[0] = mappings[0].model_copy(update={"condition_id": "absent"})
        else:
            mappings.append(mappings[0])
        review = review.model_copy(update={"settlement_mappings": tuple(mappings)})
    assert settlement_issues(review, *definitions)
    match = match_markets(markets, [review], definitions)[0]
    assert match.status == "candidate"
    assert not evaluate(match, *markets, books, Settings(_env_file=None), utcnow()).opportunities


async def test_policy_evidence_must_exist_in_bound_market_rules(fixture_market):
    markets, _, _, definitions = live_pair(fixture_market)
    policies = list(definitions[0].settlement_policies)
    policies[0] = policies[0].model_copy(
        update={
            "evidence": policies[0].evidence.model_copy(
                update={"quote": "An invented cancellation clause not present in the rules"}
            )
        }
    )
    changed = definitions[0].model_copy(update={"settlement_policies": tuple(policies)})
    assert "evidence_not_found:settlement_policy:cancellation" in evidence_issues(
        markets[0], changed
    )


async def test_one_sided_cancellation_must_be_modeled_and_can_eliminate_profit(fixture_market):
    from arbbot.domain import JointSettlementCase

    markets, books, review, definitions = live_pair(fixture_market)
    scenarios = list(review.scenarios)
    cases = [review.joint_settlement_cases[0]]
    for side in ("left", "right"):
        for outcome, normal in (("yes", Decimal(1)), ("no", Decimal(0))):
            name = f"{side}_only_cancelled_other_{outcome}"
            scenarios.append(
                Scenario(
                    name=name,
                    left_yes="0.5" if side == "left" else normal,
                    left_no="0.5" if side == "left" else 1 - normal,
                    right_yes="0.5" if side == "right" else normal,
                    right_no="0.5" if side == "right" else 1 - normal,
                )
            )
            cases.append(
                JointSettlementCase(
                    left_state="cancellation:cancelled" if side == "left" else f"normal_{outcome}",
                    right_state="cancellation:cancelled"
                    if side == "right"
                    else f"normal_{outcome}",
                    scenario=name,
                )
            )
    reviewed = review.model_copy(
        update={"scenarios": tuple(scenarios), "joint_settlement_cases": tuple(cases)}
    )
    assert not settlement_issues(reviewed, *definitions)
    match = match_markets(markets, [reviewed], definitions)[0]
    assert match.status == "verified"
    assert not evaluate(match, *markets, books, Settings(_env_file=None), utcnow()).opportunities


async def test_joint_exclusion_requires_current_policy_evidence(fixture_market):
    _, _, review, definitions = live_pair(fixture_market)
    cases = list(review.joint_settlement_cases)
    cases[1] = cases[1].model_copy(update={"left_evidence_policies": ("fallback",)})
    policies = list(definitions[0].settlement_policies)
    policies[1] = policies[1].model_copy(update={"status": "unknown"})
    definitions[0] = definitions[0].model_copy(update={"settlement_policies": tuple(policies)})
    reviewed = review.model_copy(update={"joint_settlement_cases": tuple(cases)})
    assert "joint_exclusion_evidence_invalid:left:fallback" in settlement_issues(
        reviewed, *definitions
    )
