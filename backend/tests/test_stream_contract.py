from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from arbbot.domain import Level
from arbbot.streams.base import BookState
from arbbot.streams.models import Delta, Disconnected, Snapshot


def delta(book, sequence, *, previous=None, **changes):
    return Delta(
        **{
            "epoch": "first",
            "sequence": sequence,
            "previous_sequence": sequence - 1 if previous is None else previous,
            "market_id": book.market_id,
            "mode": book.mode,
            "received_at": book.received_at + timedelta(seconds=sequence),
            "source_at": None,
            "raw": {"sequence": sequence},
            "changes": [{"outcome": "yes", "price": "0.2", "size": str(sequence)}],
            **changes,
        }
    )


async def test_snapshot_reconstructs_book_and_requires_connection(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    snapshot = Snapshot(epoch="first", sequence=1, book=book)
    assert state.accept(snapshot) == "ignored_epoch"
    assert state.eligible_book(book.received_at, 30) is None
    state.connect("first")
    assert state.eligible_book(book.received_at, 30) is None
    assert state.accept(snapshot) == "synchronized"
    recovered = state.eligible_book(book.received_at, 30)
    assert recovered == book and recovered.id == book.id
    recovered.raw["tampered"] = True
    assert "tampered" not in state.eligible_book(book.received_at, 30).raw
    assert state.eligible_book(book.received_at + timedelta(seconds=30), 30) is None


async def test_absolute_updates_deletions_and_duplicates_do_not_refresh(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    state.connect("first")
    state.accept(Snapshot(epoch="first", sequence=1, book=book))
    event = delta(
        book,
        2,
        changes=[
            {"outcome": "yes", "price": "0.2", "size": "7"},
            {"outcome": "no", "price": book.no_asks[0].price, "size": "0"},
        ],
    )
    assert state.accept(event) == "applied"
    result = state.eligible_book(event.received_at, 30)
    assert Level(price=Decimal("0.2"), size=Decimal("7")) in result.yes_asks
    assert book.no_asks[0].price not in {level.price for level in result.no_asks}
    replay = event.model_copy(update={"received_at": event.received_at + timedelta(seconds=10)})
    assert state.accept(replay) == "duplicate"
    assert state.eligible_book(replay.received_at, 30).received_at == event.received_at
    conflict = event.model_copy(update={"raw": {"different": True}})
    assert state.accept(conflict) == "resync_required"
    assert state.reason == "conflicting_duplicate"
    assert state.eligible_book(replay.received_at, 30) is None


async def test_gap_replay_and_snapshot_replacement(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    state.connect("first")
    state.accept(Snapshot(epoch="first", sequence=1, book=book))
    assert state.accept(delta(book, 3)) == "resync_required"
    assert state.reason == "sequence_gap"
    assert state.eligible_book(book.received_at, 30) is None
    snapshot = Snapshot(
        epoch="first",
        sequence=2,
        book=book.model_copy(update={"received_at": book.received_at + timedelta(seconds=5)}),
    )
    assert state.accept(snapshot) == "synchronized"
    result = state.eligible_book(snapshot.book.received_at, 30)
    assert state.sequence == 3
    assert result.received_at == snapshot.book.received_at
    assert Level(price=Decimal("0.2"), size=Decimal(3)) in result.yes_asks
    assert state.accept(Snapshot(epoch="first", sequence=10, book=snapshot.book)) == "synchronized"
    assert state.eligible_book(snapshot.book.received_at, 30) == snapshot.book


async def test_pre_snapshot_buffer_orders_events_and_discards_covered_updates(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    state.connect("first")
    assert state.accept(delta(book, 3)) == "buffered"
    assert state.accept(delta(book, 2)) == "buffered"
    assert state.accept(delta(book, 2)) == "duplicate"
    assert state.accept(Snapshot(epoch="first", sequence=1, book=book)) == "synchronized"
    assert state.sequence == 3
    # New authoritative snapshot replaces all old levels, never merges a stale remainder.
    state.invalidate("integrity_failure")
    assert state.accept(delta(book, 4)) == "buffered"
    snapshot = book.model_copy(
        update={
            "yes_asks": (),
            "no_asks": (),
            "received_at": book.received_at + timedelta(seconds=5),
        }
    )
    assert state.accept(Snapshot(epoch="first", sequence=5, book=snapshot)) == "synchronized"
    assert state.eligible_book(snapshot.received_at, 30).yes_asks == ()


@pytest.mark.parametrize("bounds", [{"max_buffer": 1}, {"max_buffer_bytes": 1}])
async def test_overflow_requires_snapshot_covering_discarded_events(fixture_market, bounds):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0], **bounds)
    state.connect("first")
    state.accept(delta(book, 2))
    assert state.accept(delta(book, 3)) == "resync_required"
    assert state.reason == "buffer_overflow"
    assert state.accept(Snapshot(epoch="first", sequence=1, book=book)) == "out_of_order"
    assert state.eligible_book(book.received_at, 30) is None
    assert state.accept(Snapshot(epoch="first", sequence=3, book=book)) == "synchronized"


async def test_disconnect_reconnect_epoch_and_sequence_reset(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    state.connect("first")
    state.accept(Snapshot(epoch="first", sequence=100, book=book))
    assert state.accept(Disconnected(epoch="first", reason="transport_error")) == "disconnected"
    assert state.eligible_book(book.received_at, 30) is None
    assert state.accept(Snapshot(epoch="first", sequence=101, book=book)) == "ignored_epoch"
    with pytest.raises(ValueError):
        state.connect("first")
    state.connect("second")
    assert state.accept(delta(book, 101)) == "ignored_epoch"
    assert state.accept(Snapshot(epoch="second", sequence=0, book=book)) == "synchronized"


async def test_missing_replay_event_requires_newer_snapshot(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0])
    state.connect("first")
    state.accept(delta(book, 4))
    assert state.accept(Snapshot(epoch="first", sequence=1, book=book)) == "resync_required"
    assert state.accept(Snapshot(epoch="first", sequence=2, book=book)) == "out_of_order"
    assert state.eligible_book(book.received_at, 30) is None
    assert state.accept(Snapshot(epoch="first", sequence=4, book=book)) == "synchronized"


async def test_timestamp_regression_identity_and_missing_source_fail_conservatively(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id].model_copy(update={"source_at": books[markets[0].id].received_at})
    state = BookState(markets[0])
    state.connect("first")
    state.accept(Snapshot(epoch="first", sequence=1, book=book))
    assert state.accept(delta(book, 2)) == "applied"
    assert state.eligible_book(book.received_at + timedelta(seconds=30), 30) is None
    assert (
        state.accept(delta(book, 3, source_at=book.source_at - timedelta(seconds=1)))
        == "resync_required"
    )
    assert state.reason == "timestamp_regression"
    state.connect("second")
    wrong = book.model_copy(update={"mode": "live"})
    assert state.accept(Snapshot(epoch="second", sequence=1, book=wrong)) == "resync_required"
    assert state.reason == "identity_mismatch"


async def test_event_and_level_limits_and_invalid_nested_models(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    for bounds, reason in [
        ({"max_event_bytes": 1}, "event_overflow"),
        ({"max_levels": 1}, "level_overflow"),
    ]:
        state = BookState(markets[0], **bounds)
        state.connect("first")
        assert state.accept(Snapshot(epoch="first", sequence=1, book=book)) == "resync_required"
        assert state.reason == reason
    state = BookState(markets[0])
    state.connect("first")
    forged = book.model_copy(update={"min_order_size": Decimal("-1")})
    assert state.accept(Snapshot(epoch="first", sequence=1, book=forged)) == "resync_required"
    assert state.reason == "invalid_event"
    with pytest.raises(ValidationError):
        delta(book, 2, previous=2)
    with pytest.raises(ValidationError):
        delta(book, 2, changes=[])


async def test_old_events_and_future_books_are_not_rejuvenated(fixture_market):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0], max_buffer=1)
    state.connect("first")
    state.accept(Snapshot(epoch="first", sequence=1, book=book))
    state.accept(delta(book, 2))
    assert state.accept(Snapshot(epoch="first", sequence=1, book=book)) == "out_of_order"
    future = book.model_copy(update={"received_at": book.received_at + timedelta(seconds=60)})
    state.accept(Snapshot(epoch="first", sequence=3, book=future))
    assert state.eligible_book(book.received_at, 30) is None


@pytest.mark.parametrize("invalid", [False, True])
async def test_discarded_untrusted_update_requires_new_subscription(fixture_market, invalid):
    markets, books, *_ = fixture_market
    book = books[markets[0].id]
    state = BookState(markets[0], max_event_bytes=10000)
    state.connect("first")
    snapshot = Snapshot(epoch="first", sequence=1, book=book)
    assert state.accept(snapshot) == "synchronized"
    event = delta(book, 2, raw={"payload": "x" * 10001})
    if invalid:
        event = delta(book, 2).model_copy(update={"previous_sequence": -1})
    state.accept(event)
    state.accept(snapshot)
    assert state.eligible_book(book.received_at, 30) is None
    assert state.status == "disconnected"
    state.connect("second")
    assert state.accept(Snapshot(epoch="second", sequence=0, book=book)) == "synchronized"
