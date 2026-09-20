import asyncio
import json
from datetime import timedelta
from decimal import Decimal, localcontext

import pytest
from pydantic import TypeAdapter, ValidationError

from arbbot.domain import utcnow
from arbbot.fees.base import quote_fees
from arbbot.fees.models import FeeCharge, FeeQuote, FeeRequest, FeeResult, FeeUnavailable


def request(**changes):
    return FeeRequest(
        **{
            "mode": "live",
            "venue": "kalshi",
            "market_id": "kalshi:test",
            "outcome": "yes",
            "side": "buy",
            "liquidity": "taker",
            "settlement_asset": "USD",
            "quantity": "10",
            "fills": [{"price": "0.3", "quantity": "4"}, {"price": "0.4", "quantity": "6"}],
            **changes,
        }
    )


def charge(**changes):
    return FeeCharge(
        **{
            "name": "fee",
            "basis": "price_dependent",
            "scope": "order",
            "amount": "0.011",
            "rounding_increment": "0.01",
            **changes,
        }
    )


def quote(req=None, now=None, **changes):
    now = now or utcnow()
    return FeeQuote(
        **{
            "request": req or request(),
            "as_of": now,
            "source": "synthetic test policy",
            "policy_version": "fixture/1",
            "observed_at": now - timedelta(seconds=1),
            "effective_at": now - timedelta(days=1),
            "expires_at": now + timedelta(seconds=30),
            "charges": [charge()],
            **changes,
        }
    )


def test_exact_rounding_components_and_serialization():
    charges = [
        charge(name="fixed", basis="fixed", amount="0.1"),
        charge(name="quantity", basis="quantity", amount="0.200000000001"),
        charge(name="price", amount="0.051", rounding_increment="0.05"),
    ]
    result = quote(charges=charges)
    assert result.total == Decimal("0.41")
    payload = json.loads(result.model_dump_json())
    assert payload["total"] == "0.41"
    assert payload["charges"][2]["rounded_amount"] == "0.10"
    assert payload["request"]["fills"][0]["price"] == "0.3"
    assert TypeAdapter(FeeResult).validate_json(result.model_dump_json(round_trip=True)) == result


def test_per_fill_rounding_differs_from_order_rounding():
    assert quote(charges=[charge(scope="fill", fill_index=i) for i in (0, 1)]).total == Decimal(
        "0.04"
    )
    assert quote(charges=[charge(amount="0.022")]).total == Decimal("0.03")


def test_arithmetic_is_independent_of_ambient_precision():
    with localcontext() as context:
        context.prec = 3
        result = quote(charges=[charge(amount="123456.123456789012")])
        assert result.total == Decimal("123456.13")


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": "11"},
        {"quantity": "0"},
        {"quantity": 10.0},
        {"quantity": True},
        {"market_id": "polymarket:test"},
        {"fills": []},
        {"fills": [{"price": "1.1", "quantity": "10"}]},
        {"fills": [{"price": "NaN", "quantity": "10"}]},
        {"fills": [{"price": 0.3, "quantity": "10"}]},
    ],
)
def test_invalid_request(changes):
    with pytest.raises(ValidationError):
        request(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "-1"},
        {"amount": "Infinity"},
        {"amount": 0.1},
        {"rounding_increment": "0"},
        {"scope": "fill"},
        {"fill_index": 0},
    ],
)
def test_invalid_charges(changes):
    with pytest.raises(ValidationError):
        charge(**changes)


def test_zero_fees_are_explicit_not_a_default():
    with pytest.raises(ValidationError, match="Zero fees"):
        quote(charges=[charge(amount="0")])
    assert (
        quote(charges=[charge(amount="0")], zero_fee_reason="Verified zero-fee fixture").total == 0
    )
    with pytest.raises(ValidationError):
        quote(charges=[])


def test_stale_future_and_unbound_quotes_rejected():
    now = utcnow()
    for changes in [
        {"expires_at": now},
        {"observed_at": now + timedelta(seconds=1)},
        {"effective_at": now + timedelta(seconds=1)},
        {"source": " "},
        {"charges": [charge(scope="fill", fill_index=2)]},
        {"charges": [charge(), charge()]},
    ]:
        with pytest.raises(ValidationError):
            quote(now=now, **changes)


async def test_missing_unsupported_stale_and_provider_errors_never_zero():
    req, now = request(), utcnow()
    missing = await quote_fees(None, req, as_of=now)
    assert missing.status == "unavailable"
    assert "total" not in missing.model_dump()
    for reason in ("unsupported", "stale", "not_yet_effective", "missing_policy"):

        class Provider:
            def __init__(self, reason):
                self.reason = reason

            async def quote(self, request, *, as_of):
                return FeeUnavailable(request=request, as_of=as_of, reason=self.reason)

        result = await quote_fees(Provider(reason), req, as_of=now)
        assert result.reason == reason
        assert TypeAdapter(FeeResult).validate_json(result.model_dump_json()) == result

    class Broken:
        async def quote(self, request, *, as_of):
            raise RuntimeError("private provider response")

    result = await quote_fees(Broken(), req, as_of=now)
    assert result.reason == "provider_error"
    assert "private" not in result.model_dump_json()


async def test_provider_result_revalidation_and_binding():
    req, now = request(), utcnow()

    class Provider:
        def __init__(self, result):
            self.result = result

        async def quote(self, request, *, as_of):
            return self.result

    good = quote(req, now)
    assert (await quote_fees(Provider(good), req, as_of=now)).total == Decimal("0.02")
    for invalid in [
        good.model_copy(update={"expires_at": now}),
        quote(request(side="sell"), now),
        quote(req, now + timedelta(seconds=1)),
        None,
        {"status": "available", "total": "0"},
    ]:
        assert (await quote_fees(Provider(invalid), req, as_of=now)).reason == "invalid_quote"


async def test_cancellation_propagates():
    class Provider:
        async def quote(self, request, *, as_of):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await quote_fees(Provider(), request(), as_of=utcnow())
