"""Check recorded negative-risk evidence and payoff examples without relaxing eligibility."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from arbbot.domain import CostPolicy, Review, Scenario, digest, utcnow
from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket import PolymarketAdapter

ROOT = Path(__file__).parent / "fixtures" / "negative_risk"
RECORDS = json.loads((ROOT / "recorded.json").read_text())
LABELS = json.loads((ROOT / "labels.json").read_text())
PAYOFFS = json.loads((ROOT / "payoffs.json").read_text())

ONE = Decimal(1)
GROUPS = {
    record["payload"].get("event_ticker") or "polymarket:" + record["payload"]["id"]: record
    for record in RECORDS
}


def questions(key):
    return GROUPS[key]["payload"]["markets"]


def group_fingerprint(event):
    """Identity of the whole outcome set, which no current model field records."""
    return digest(
        sorted(
            (str(market["id"]), market.get("groupItemTitle") or "") for market in event["markets"]
        )
    )


@pytest.mark.parametrize("key", sorted(GROUPS))
def test_recorded_group_evidence_is_immutable_and_independently_labeled(key):
    payload = GROUPS[key]["payload"]
    label = LABELS[key]
    assert digest(payload) == label["payload_sha256"]
    assert len(payload["markets"]) == label["question_count"]
    if label["mechanism"] == "polymarket_negative_risk":
        assert payload["negRisk"] is True
        assert payload["negRiskAugmented"] == label["augmented"]
        assert payload["negRiskMarketID"] == label["group_id"]
        other = [m for m in payload["markets"] if m.get("negRiskOther")]
        assert bool(other) == label["explicit_other"]
        placeholders = [m["groupItemTitle"] for m in payload["markets"]]
        assert [t for t in placeholders if t.startswith("Person ")] == label[
            "placeholder_questions"
        ]
    else:
        assert payload["mutually_exclusive"] == label["mutually_exclusive"]
        assert payload["collateral_return_type"] == label["collateral_return_type"]


@pytest.mark.parametrize(
    "key", sorted(k for k, v in LABELS.items() if v["mechanism"] == "polymarket_negative_risk")
)
def test_negative_risk_questions_are_excluded_only_by_the_group_flag(key):
    """Each question already has unit binary shape, so exclusion is a deliberate policy."""
    assert LABELS[key]["supported_by_adapter"] is False
    for market in questions(key):
        assert PolymarketAdapter.supported(market) is False
        assert PolymarketAdapter.supported({**market, "negRisk": False}) is True
        assert json.loads(market["outcomes"]) == ["Yes", "No"]
        assert len(json.loads(market["clobTokenIds"])) == 2


def test_negative_risk_books_remain_rejected():
    market = PolymarketAdapter.normalize_market(
        {**questions("polymarket:606422")[0], "negRisk": False}
    )
    book = {
        "asset_id": market.tokens["yes"],
        "timestamp": "1790000000000",
        "neg_risk": True,
        "asks": [],
        "min_order_size": "5",
    }
    with pytest.raises(ValueError, match="Negative-risk books are not supported"):
        PolymarketAdapter.normalize_book(market, book, {**book, "asset_id": market.tokens["no"]})


@pytest.mark.parametrize(
    "key", sorted(k for k, v in LABELS.items() if v["mechanism"] == "kalshi_mutually_exclusive")
)
def test_mutually_exclusive_kalshi_groups_are_ingested_without_group_evidence(key):
    """mve_filter excludes combinations, not mutually exclusive groups, so these are ingested."""
    assert LABELS[key]["supported_by_adapter"] is True
    for item in questions(key):
        assert item["market_type"] == "binary"
        assert Decimal(str(item["notional_value_dollars"])) == 1
        market = KalshiAdapter.normalize_market(item)
        assert "mutually_exclusive" not in market.settlement_details
        assert "collateral_return_type" not in market.settlement_details


def test_recorded_bracket_rules_omit_a_boundary_present_in_the_label():
    """Authoritative Kalshi rule text is weaker than the bucket label for the cut bracket."""
    markets = {item["ticker"]: item for item in questions("KXFEDDECISION-26OCT")}
    cut = markets["KXFEDDECISION-26OCT-C26"]
    hike = markets["KXFEDDECISION-26OCT-H26"]
    assert cut["yes_sub_title"] == "Cut >25bps"
    assert ">" not in cut["rules_primary"]
    assert ">25bps" in hike["rules_primary"]


def test_clarifying_a_placeholder_does_not_invalidate_sibling_approvals():
    """Reviewed terms cover one question, so a group edit cannot expire a sibling approval."""
    event = GROUPS["polymarket:81557"]["payload"]
    by_title = {market["groupItemTitle"]: market for market in event["markets"]}
    residual = by_title["Other"]
    before = PolymarketAdapter.normalize_market(residual).terms_hash
    clarified = {
        **by_title["Person H"],
        "groupItemTitle": "Yoav Gallant",
        "question": "Will Yoav Gallant be the next Prime Minister of Israel?",
    }
    updated = {
        **event,
        "markets": [clarified if m["id"] == clarified["id"] else m for m in event["markets"]],
    }
    assert group_fingerprint(updated) != group_fingerprint(event)
    unchanged = next(m for m in updated["markets"] if m["id"] == residual["id"])
    assert unchanged == residual
    assert PolymarketAdapter.normalize_market(unchanged).terms_hash == before
    assert "another person" in residual["question"]


@pytest.mark.parametrize("case", PAYOFFS["conversion"]["cases"], ids=lambda c: c["name"])
def test_documented_conversion_payoffs_reproduce_recorded_examples(case):
    amount = Decimal(case["amount"])
    selected = Decimal(case["converted"])
    collateral = amount * (selected - ONE)
    received_yes = amount - (amount * Decimal(case["fee_bips"]) / Decimal(10_000))
    computed = {
        "winner_inside_converted_set": (amount * (selected - ONE), collateral),
        "winner_outside_converted_set": (amount * selected, collateral + received_yes),
        "no_winner": (amount * selected, collateral),
    }
    for state, (held, converted) in computed.items():
        expected = case["states"][state]
        assert held == Decimal(expected["held_no"]), state
        assert converted == Decimal(expected["after_conversion"]), state
    inside = computed["winner_inside_converted_set"]
    assert inside[0] == inside[1]
    assert computed["no_winner"][0] - computed["no_winner"][1] == amount


@pytest.mark.parametrize("pair", PAYOFFS["pairs"], ids=lambda p: p["name"])
def test_evidenced_states_break_pairs_that_look_complementary(pair):
    """Ordinary YES and NO scenarios alone hide a state where a direction pays nothing."""
    sides = {"left_yes_right_no": ("yes", "no"), "left_no_right_yes": ("no", "yes")}

    def payout(state, left_side, right_side):
        left, right = Decimal(state["left_yes"]), Decimal(state["right_yes"])
        return (left if left_side == "yes" else ONE - left) + (
            right if right_side == "yes" else ONE - right
        )

    ordinary = [state for state in pair["states"] if state["ordinary"]]
    assert len(ordinary) == 2
    assert any(not state["ordinary"] for state in pair["states"])
    for direction, (left_side, right_side) in sides.items():
        expected = pair["directions"][direction]
        assert min(payout(s, left_side, right_side) for s in ordinary) == Decimal(
            expected["ordinary_only_worst_payout"]
        )
        assert min(payout(s, left_side, right_side) for s in pair["states"]) == Decimal(
            expected["worst_payout"]
        )
    assert pair["complementary_under_ordinary_states"] is True
    assert any(Decimal(pair["directions"][direction]["worst_payout"]) < ONE for direction in sides)


def test_review_accepts_scenarios_that_omit_an_evidenced_divergence():
    """The ordinary-outcome requirement does not force reviewers to enumerate group states."""
    costs = CostPolicy(
        fee_per_contract="0",
        fixed_fee="0",
        min_order_size="1",
        min_notional="0",
        cost_fx="1",
        payout_fx="1",
        evidence="Recorded negative-risk research fixture, not a venue fee schedule.",
    )
    review = Review(
        left_id="kalshi:KXFEDDECISION-26OCT-C25",
        right_id="polymarket:2589811",
        left_terms_hash="a" * 64,
        right_terms_hash="b" * 64,
        status="verified",
        reviewer="research",
        rationale="Both questions name a 25 basis point cut at the same decision.",
        resolution_sources="Federal Reserve statement for the October 2026 meeting.",
        deadlines_and_timezones="Both settle after the October 28, 2026 decision.",
        cancellation_and_exceptions="Ordinary outcomes only; bracket rounding is not covered.",
        expires_at=utcnow() + timedelta(days=1),
        scenarios=(
            Scenario(name="yes", left_yes="1", right_yes="1"),
            Scenario(name="no", left_yes="0", right_yes="0"),
        ),
        left_costs=costs,
        right_costs=costs,
    )
    assert {scenario.name for scenario in review.scenarios} == {"yes", "no"}
    divergent = next(
        state
        for pair in PAYOFFS["pairs"]
        if pair["name"] == "fed_october_25bps_bucket"
        for state in pair["states"]
        if not state["ordinary"]
    )
    assert Decimal(divergent["left_yes"]) != Decimal(divergent["right_yes"])
    assert not any(
        (Decimal(divergent["left_yes"]), Decimal(divergent["right_yes"]))
        == (scenario.left_yes, scenario.right_yes)
        for scenario in review.scenarios
    )
