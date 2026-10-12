"""Replay is explicit, read-only, and preserves historical financial identifiers."""

from arbbot.domain import Book, digest
from tests.test_polymarket_us import pair


async def test_historical_quote_payload_keeps_original_identifier(fixture_market):
    _, books, _, _ = fixture_market
    for book in books.values():
        historical = book.model_dump(mode="json", exclude={"feed_origin"})
        old_id = digest(historical)
        restored = Book.model_validate(historical)
        assert restored.id == old_id
        assert restored.feed_origin == "exchange"
        recorded = restored.model_copy(update={"feed_origin": "synthetic_recording"})
        assert recorded.id != old_id


def test_historical_us_terms_do_not_change_when_empty_price_ranges_are_added():
    market = pair()[1]
    constraints = market.instrument_constraints.model_dump(mode="json", exclude={"price_ranges"})
    legacy_hash = digest(
        {
            "title": market.title,
            "rules": market.rules,
            "closes_at": market.closes_at.isoformat(),
            "asset": market.settlement_asset,
            "tokens": market.tokens,
            "instrument_constraints": constraints,
            "execution_semantics": market.execution_semantics.model_dump(mode="json"),
            "settlement_details": market.settlement_details,
        }
    )
    assert market.terms_hash == legacy_hash
