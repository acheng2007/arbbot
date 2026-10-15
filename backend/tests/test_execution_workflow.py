"""Synthetic financial/gating scenarios, never represented as real market evidence."""

from datetime import timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

import pytest

from arbbot.arbitrage.engine import evaluate
from arbbot.domain import ExecutionSemantics, InstrumentConstraints, Level, digest, utcnow
from arbbot.execution.models import (
    AccessProfile,
    Applicability,
    Citation,
    ConfigurationWrite,
    ExecutableFeePolicy,
    ExecutionContext,
    Permission,
)
from arbbot.execution.repository import ExecutionRepository
from arbbot.fees.executable import fee_bound
from arbbot.fees.models import Fill
from arbbot.fees.refresh import kalshi_parameters
from arbbot.matching.contracts import definition_hash
from arbbot.matching.service import match_markets
from arbbot.reviews.models import Actor, ReviewValidationError, RevisionConflict
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from tests.test_contracts import definition

ACTOR = Actor(issuer="local-operator", subject="test-operator")


def policy(venue, now, **changes):
    return ExecutableFeePolicy(
        market_id=f"{venue}:synthetic",
        venue=venue,
        terms_hash="a" * 64,
        formula="us_standard" if venue == "polymarket_us" else "kalshi_quadratic",
        coefficient="0.10" if venue == "polymarket_us" else "0.07",
        minimum_execution_quantity=None if venue == "polymarket_us" else "0.01",
        balance_precision=None if venue == "polymarket_us" else "0.0001",
        account_class="standard" if venue == "polymarket_us" else "direct",
        source=Citation(
            artifact_id="b" * 64, content_hash="c" * 64, quotation="Synthetic policy evidence only"
        ),
        metadata_hash=digest({}),
        observed_at=now,
        effective_at=now,
        expires_at=now + timedelta(minutes=5),
        **changes,
    )


@pytest.mark.parametrize("precision", ["0.0001", "0.01"])
@pytest.mark.parametrize("price", ["0.0001", "0.0755", "0.50", "0.9999"])
def test_kalshi_depth_bound_dominates_fragmented_execution(precision, price):
    now, price = utcnow(), Decimal(price)
    p = policy("kalshi", now).model_copy(
        update={
            "balance_precision": precision,
            "account_class": "direct" if precision == "0.0001" else "non_direct",
        }
    )
    bound = fee_bound(p, (Fill(price=price, quantity="3"),), now)
    for partition in (
        [Decimal("0.01")] * 300,
        [Decimal("0.03")] * 100,
        [Decimal("1")] * 3,
        [Decimal("3")],
    ):
        accumulator, total = Decimal(0), Decimal(0)
        for quantity in partition:
            revenue = -price * quantity
            trade = (p.coefficient * quantity * price * (1 - price)).quantize(
                Decimal("0.000001"), rounding=ROUND_CEILING
            )
            unit = Decimal(precision)
            aligned = ((revenue - trade) / unit).to_integral_value(rounding=ROUND_FLOOR) * unit
            rounding = revenue - trade - aligned
            accumulator += rounding
            rebate = (
                min(
                    (accumulator / unit).to_integral_value(rounding=ROUND_FLOOR),
                    ((trade + rounding) / unit).to_integral_value(rounding=ROUND_FLOOR),
                )
                * unit
            )
            accumulator -= rebate
            total += trade + rounding - rebate
        assert bound >= total


def test_us_cumulative_cap_is_partition_independent_and_half_even():
    now = utcnow()
    p = policy("polymarket_us", now)
    assert fee_bound(p, (Fill(price="0.5", quantity="1"),), now) == Decimal("0.02")
    assert fee_bound(p, (Fill(price="0.5", quantity="0.5"),) * 2, now) == Decimal("0.02")
    assert fee_bound(p, (Fill(price="0.5", quantity="1"),), p.expires_at) is None
    unknown = policy("kalshi", now).model_copy(update={"minimum_execution_quantity": None})
    assert fee_bound(unknown, (Fill(price="0.5", quantity="1"),), now) is None


async def test_us_conditional_profit_unprofit_short_and_unknown_gates(fixture_market, database):
    settings, _, _ = database
    originals, old_books, old_review, _ = fixture_market
    now = utcnow()
    markets, books = [], {}
    for index, original in enumerate(originals):
        venue = "kalshi" if index == 0 else "polymarket_us"
        market = original.model_copy(
            update={
                "id": f"{venue}:synthetic",
                "venue": venue,
                "mode": "live",
                "settlement_asset": "USD",
                "settlement_details": {"source_status": "captured"},
                "instrument_constraints": InstrumentConstraints(
                    price_increment="0.01",
                    quantity_increment="0.01",
                    minimum_quantity="1",
                    payout_evidence="Synthetic unit payout",
                ),
                "execution_semantics": ExecutionSemantics(
                    yes_action="buy_instrument" if index else "buy_yes",
                    no_action="short_instrument" if index else "buy_no",
                    no_native_price_is_complement=bool(index),
                    gross_short_collateral_per_contract="1" if index else None,
                ),
            }
        )
        markets.append(market)
        books[market.id] = old_books[original.id].model_copy(
            update={
                "market_id": market.id,
                "mode": "live",
                "source_at": now,
                "received_at": now,
                "yes_asks": (Level(price="0.1" if index == 0 else "0.9", size="10"),),
                "no_asks": (Level(price="0.9" if index == 0 else "0.1", size="10"),),
            }
        )
    definitions = [definition(m) for m in markets]
    review = old_review.model_copy(
        update={
            "left_id": markets[0].id,
            "right_id": markets[1].id,
            "left_terms_hash": markets[0].terms_hash,
            "right_terms_hash": markets[1].terms_hash,
            "left_definition_hash": definition_hash(definitions[0]),
            "right_definition_hash": definition_hash(definitions[1]),
        }
    )
    match = match_markets(markets, [review], definitions)[0]
    assert match.status == "verified"
    context = ExecutionContext(
        access_revision_id="access",
        applicability_revision_ids=("a", "b"),
        fee_revision_ids=("c", "d"),
        policies=tuple(
            policy(m.venue, now).model_copy(update={"terms_hash": m.terms_hash}) for m in markets
        ),
        short_allowed_market_ids=(markets[1].id,),
        valid_until=now + timedelta(minutes=1),
    )
    missing = evaluate(match, *markets, books, settings, now)
    assert missing.status == "blocked" and "installation_access_unknown" in missing.blocked_reasons
    result = evaluate(match, *markets, books, settings, now, context)
    assert result.status == "profitable", result.blocked_reasons
    leg = result.opportunities[0].legs[1]
    assert leg.native_action == "short_instrument" and leg.native_price == Decimal("0.9")
    assert leg.short_proceeds == Decimal("9") and leg.gross_collateral == Decimal("10")
    assert result.opportunities[0].capital_required >= Decimal("11")
    for mid in books:
        books[mid] = books[mid].model_copy(
            update={
                "yes_asks": (Level(price="0.6", size="10"),),
                "no_asks": (Level(price="0.6", size="10"),),
            }
        )
    result = evaluate(match, *markets, books, settings, now, context)
    assert result.status == "unprofitable" and result.best_calculation.net_profit < 0
    stale = evaluate(match, *markets, books, settings, now + timedelta(minutes=1), context)
    assert stale.status == "invalid"


async def test_access_revision_conflict_and_sanitized_blocking(database, fixture_market):
    _, db, _ = database
    repo = ExecutionRepository(db)
    profile = AccessProfile(
        jurisdiction="US-NY",
        status="verified",
        permissions=(
            Permission(
                venue="kalshi",
                market_ids=("kalshi:synthetic",),
                short_allowed=False,
                fee_account_class="non_direct",
            ),
        ),
        supporting_evidence=("Private operator attestation",),
        expires_at=utcnow() + timedelta(hours=1),
    )
    request = ConfigurationWrite(value=profile, reason="Reviewed installation product access")
    first = await repo.save("live", request, ACTOR)
    with pytest.raises(RevisionConflict):
        await repo.save("live", request, ACTOR)
    async with db.sessions() as session:
        context = await repo.context(session, "live", fixture_market[0])
    assert context.blocked_reasons and not hasattr(context, "supporting_evidence")
    assert first.actor.subject == "test-operator"


async def test_applicability_requires_exact_captured_quotes_and_current_terms(
    database, fixture_market
):
    _, db, storage = database
    market = fixture_market[0][0]
    await storage.save_market(market)
    sources = SourceRepository(db)
    capture = SourceCapture(
        mode=market.mode,
        venue=market.venue,
        market_id=market.id,
        url="https://assets.kalshi.com/synthetic.pdf",
        label="synthetic_terms",
        content_type="text/plain",
        content=b"Synthetic product specification and amendment inventory.",
        retrieved_at=utcnow(),
    )
    source = await sources.record(capture)
    citation = Citation(
        artifact_id=source.id,
        content_hash=source.content_digest,
        quotation="Synthetic product specification",
    )
    app = Applicability(
        market_id=market.id,
        terms_hash=market.terms_hash,
        product_id="synthetic",
        status="verified",
        specifications=(citation,),
        amendment_inventory=citation,
        rationale="Synthetic isolated test applicability",
        expires_at=utcnow() + timedelta(hours=1),
    )
    repo = ExecutionRepository(db)
    first = await repo.save(
        "simulation", ConfigurationWrite(value=app, reason="Review synthetic evidence"), ACTOR
    )
    bad = app.model_copy(
        update={
            "terms_hash": first.value.terms_hash,
            "specifications": (
                citation.model_copy(update={"quotation": "Invented quotation absent from source"}),
            ),
        }
    )
    with pytest.raises(ReviewValidationError):
        await repo.save(
            "simulation",
            ConfigurationWrite(
                value=bad, expected_revision_id=first.id, reason="Reject invented source quotation"
            ),
            ACTOR,
        )
    assert first.value.specifications[0].content_hash == source.content_digest


def test_current_kalshi_overrides_and_scheduled_deadlines():
    now = utcnow()
    metadata = {
        "market": {"market_type": "binary", "notional_value_dollars": "1", "event_ticker": "E"},
        "event": {"event_ticker": "E", "series_ticker": "S"},
        "series": {"ticker": "S", "fee_type": "quadratic", "fee_multiplier": "1"},
        "series_changes": [],
        "event_changes": [
            {
                "event_ticker": "E",
                "scheduled_ts": (now - timedelta(seconds=1)).isoformat(),
                "fee_type_override": "quadratic",
                "fee_multiplier_override": "2",
            },
            {
                "event_ticker": "E",
                "scheduled_ts": (now + timedelta(seconds=20)).isoformat(),
                "fee_type_override": None,
                "fee_multiplier_override": None,
            },
        ],
    }
    coefficient, expiry = kalshi_parameters(metadata, now)
    assert coefficient == Decimal("0.14") and expiry == now + timedelta(seconds=20)


async def test_missing_us_fee_artifact_returns_validation_error(database):
    from tests.test_polymarket_us import pair

    _, db, storage = database
    market = pair()[1]
    await storage.save_market(market)
    now = utcnow()
    value = policy("polymarket_us", now).model_copy(
        update={"market_id": market.id, "terms_hash": market.terms_hash}
    )
    with pytest.raises(ReviewValidationError):
        await ExecutionRepository(db).save(
            "live",
            ConfigurationWrite(
                value=value, reason="Reject fee policy with missing recorded evidence"
            ),
            ACTOR,
        )


async def test_validation_only_checks_repositories_without_import(database):
    _, db, _ = database
    profile = AccessProfile(
        jurisdiction="SYNTHETIC",
        status="verified",
        permissions=(
            Permission(
                venue="kalshi",
                market_ids=("kalshi:synthetic",),
                short_allowed=False,
                fee_account_class="direct",
            ),
        ),
        supporting_evidence=("Synthetic operator evidence",),
        expires_at=utcnow() + timedelta(hours=1),
    )
    request = ConfigurationWrite(value=profile, reason="Validate synthetic installation profile")
    await ExecutionRepository(db, validate_only=True).save("live", request, ACTOR)
    store = ExecutionRepository(db)
    async with db.sessions() as session:
        assert await store.current(session, "live:access:installation") is None
    imported = await store.save("live", request, ACTOR)
    with pytest.raises(RevisionConflict):
        await ExecutionRepository(db, validate_only=True).save("live", request, ACTOR)
    async with db.sessions() as session:
        assert (await store.current(session, "live:access:installation")).id == imported.id


async def test_concurrent_initial_access_import_returns_revision_conflict(database):
    import asyncio

    _, db, _ = database
    profile = AccessProfile(
        jurisdiction="SYNTHETIC",
        status="verified",
        permissions=(
            Permission(
                venue="kalshi",
                market_ids=("kalshi:synthetic",),
                short_allowed=False,
                fee_account_class="direct",
            ),
        ),
        supporting_evidence=("Synthetic operator evidence",),
        expires_at=utcnow() + timedelta(hours=1),
    )
    request = ConfigurationWrite(value=profile, reason="Concurrent initial access import")
    results = await asyncio.gather(
        *(ExecutionRepository(db).save("live", request, ACTOR) for _ in range(2)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, RevisionConflict) for result in results) == 1
    assert sum(not isinstance(result, Exception) for result in results) == 1
