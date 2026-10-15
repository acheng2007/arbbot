import json
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from arbbot.domain import digest
from arbbot.fees.base import quote_fees
from arbbot.fees.models import FeeRequest
from arbbot.fees.polymarket import PolymarketFeeProvider, policy_from_payload

RECORDS = json.loads((Path(__file__).parent / "fixtures/polymarket_fees/recorded.json").read_text())
NOW = datetime.fromisoformat(RECORDS[0]["captured_at"])
PAYLOAD_DIGESTS = {
    "4620900": "afb6b0969a220fc2e0be14a4fa3c05e1623238e141b48f0fa8c4ad8f8ae5fe9b",
    "609655": "4c3a50b5ac2e4f5370dee518828bd90fcaba2a45036df07b3b90b6b60ad50894",
}


def policy(**changes):
    payload = {**RECORDS[0]["payload"], **changes}
    return policy_from_payload(
        payload, market_id="polymarket:4620900", mode="live", observed_at=NOW
    )


def request(price="0.5", quantity="100", **changes):
    return FeeRequest(
        **{
            "mode": "live",
            "venue": "polymarket",
            "market_id": "polymarket:4620900",
            "outcome": "yes",
            "side": "buy",
            "liquidity": "taker",
            "settlement_asset": "pUSD",
            "quantity": quantity,
            "fills": [{"price": price, "quantity": quantity}],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "price,quantity,expected",
    [
        ("0.5", "100", "1.25000"),
        ("0.1", "100", "0.45000"),
        ("0.3", "100", "1.05000"),
        ("0.7", "100", "1.05000"),
        ("0", "100", "0"),
        ("1", "100", "0"),
        ("0.1", "0.001", "0.00001"),
        ("0.5", "0.000001", "0.00001"),
    ],
)
async def test_official_linear_examples_and_conservative_boundaries(price, quantity, expected):
    result = await quote_fees(PolymarketFeeProvider(policy()), request(price, quantity), as_of=NOW)
    assert result.status == "available"
    assert result.total == Decimal(expected)
    assert isinstance(result.model_dump(mode="json")["total"], str)
    assert result.policy_version.endswith(policy().payload_digest)


@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("outcome", ["yes", "no"])
async def test_fee_curve_applies_to_each_supplied_outcome_and_trade_side(side, outcome):
    result = await quote_fees(
        PolymarketFeeProvider(policy()), request(side=side, outcome=outcome), as_of=NOW
    )
    assert result.total == Decimal("1.25")


async def test_rounding_is_per_fill_and_independent_of_global_decimal_context():
    provider = PolymarketFeeProvider(policy())
    req = request("0.1", "0.003", fills=[{"price": "0.1", "quantity": "0.001"}] * 3)
    with localcontext() as context:
        context.prec = 2
        result = await quote_fees(provider, req, as_of=NOW)
    unsplit = await quote_fees(provider, request("0.1", "0.003"), as_of=NOW)
    assert result.total == Decimal("0.00003")
    assert unsplit.total == Decimal("0.00002")


@pytest.mark.parametrize(
    "metadata,reason",
    [
        ({"feesEnabled": None}, "missing_policy"),
        ({"feeSchedule": None}, "missing_policy"),
        ({"negRisk": True}, "unsupported"),
        ({"feeSchedule": {"rate": "0.05", "exponent": 2, "takerOnly": True}}, "unsupported"),
        ({"feeSchedule": {"rate": "0.05", "exponent": 1, "takerOnly": False}}, "unsupported"),
        ({"feesEnabled": False}, "unsupported"),
    ],
)
async def test_unknown_or_conflicting_metadata_never_means_zero_fees(metadata, reason):
    result = await quote_fees(PolymarketFeeProvider(policy(**metadata)), request(), as_of=NOW)
    assert result.status == "unavailable" and result.reason == reason


async def test_explicit_disabled_fees_and_taker_only_maker_are_auditable():
    free = policy(feesEnabled=False, feeSchedule=None)
    result = await quote_fees(PolymarketFeeProvider(free), request(), as_of=NOW)
    assert result.total == 0 and "explicitly disables" in result.zero_fee_reason
    result = await quote_fees(
        PolymarketFeeProvider(policy()), request(liquidity="maker"), as_of=NOW
    )
    assert result.total == 0 and "takers only" in result.zero_fee_reason


@pytest.mark.parametrize(
    "as_of,reason",
    [
        (NOW - timedelta(seconds=1), "not_yet_effective"),
        (NOW + timedelta(seconds=300), "stale"),
    ],
)
async def test_metadata_observation_and_expiry_bound_quotes(as_of, reason):
    result = await quote_fees(PolymarketFeeProvider(policy()), request(), as_of=as_of)
    assert result.status == "unavailable" and result.reason == reason


@pytest.mark.parametrize(
    "changes",
    [{"mode": "simulation"}, {"market_id": "polymarket:609655"}, {"settlement_asset": "USD"}],
)
async def test_policy_cannot_be_reused_for_another_market_mode_or_asset(changes):
    result = await quote_fees(PolymarketFeeProvider(policy()), request(**changes), as_of=NOW)
    assert result.status == "unavailable" and result.reason == "unsupported"


def test_malformed_metadata_and_float_rates_are_rejected():
    for schedule in (
        {"rate": 0.05, "exponent": 1, "takerOnly": True},
        {"rate": "0.05", "exponent": True, "takerOnly": True},
        {"rate": "0.05", "exponent": 1},
        "unknown",
    ):
        with pytest.raises((ValueError, ValidationError)):
            policy(feeSchedule=schedule)
    with pytest.raises(ValueError, match="different market"):
        policy(id="609655")


async def test_each_recorded_market_has_its_own_policy_and_provenance():
    for record in RECORDS:
        assert digest(record["payload"]) == PAYLOAD_DIGESTS[record["payload"]["id"]]
        market_id = "polymarket:" + record["payload"]["id"]
        observed = datetime.fromisoformat(record["captured_at"])
        snapshot = policy_from_payload(
            record["payload"], market_id=market_id, mode="live", observed_at=observed
        )
        result = await quote_fees(
            PolymarketFeeProvider(snapshot), request(market_id=market_id), as_of=observed
        )
        assert result.source == record["source_url"]
        assert result.total == Decimal("1.25")


async def test_exact_decimal_exponent_representation_is_supported():
    snapshot = policy(feeSchedule={"rate": "0.05", "exponent": "1.0", "takerOnly": True})
    result = await quote_fees(PolymarketFeeProvider(snapshot), request(), as_of=NOW)
    assert result.total == Decimal("1.25")
