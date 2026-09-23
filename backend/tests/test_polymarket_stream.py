import asyncio
import json
from datetime import timedelta
from decimal import Decimal

import pytest

from arbbot.domain import utcnow
from arbbot.exchanges.polymarket import PolymarketAdapter
from arbbot.streams.polymarket import (
    MarketBooks,
    PolymarketStream,
    StreamingPolymarketAdapter,
    StreamIntegrityError,
    StreamNotReady,
)


@pytest.fixture
def market():
    return PolymarketAdapter.normalize_market(
        {
            "id": "123",
            "question": "Test event?",
            "active": True,
            "closed": False,
            "acceptingOrders": True,
            "enableOrderBook": True,
            "outcomes": ["No", "Yes"],
            "clobTokenIds": ["no", "yes"],
            "endDate": (utcnow() + timedelta(days=1)).isoformat(),
            "negRisk": False,
            "conditionId": "condition",
            "orderMinSize": "5",
        }
    )


def snapshot(token="yes", now=None):
    return {
        "event_type": "book",
        "market": "condition",
        "asset_id": token,
        "timestamp": str(int((now or utcnow()).timestamp() * 1000)),
        "bids": [{"price": "0.3", "size": "11"}],
        "asks": [{"price": "0.6", "size": "20"}, {"price": "0.5", "size": "10"}],
        "hash": "venue-hash",
    }


def delta(token="yes", now=None, **fields):
    return {
        "event_type": "price_change",
        "market": "condition",
        "timestamp": str(int((now or utcnow()).timestamp() * 1000)),
        "price_changes": [
            {
                "asset_id": token,
                "price": "0.5",
                "size": "7.125",
                "side": "SELL",
                "best_bid": "0.3",
                "best_ask": "0.5",
                **fields,
            }
        ],
    }


def seeded(market):
    state = MarketBooks([market])
    now = utcnow()
    for token in ("yes", "no"):
        state.apply(snapshot(token, now), now)
    return state


def test_absolute_updates_removal_duplicates_and_exact_provenance(market):
    state = seeded(market)
    event = delta()
    now = utcnow()
    assert state.apply(event, now)
    book = state.book(market)
    assert book.yes_asks[0].size == Decimal("7.125")  # Replace, never add.
    assert book.min_order_size == 5
    assert book.raw["transport"] == "websocket"
    assert book.raw["yes"]["last_event"] == event
    assert not state.apply(event, now + timedelta(seconds=1))
    assert state.book(market).id == book.id
    state.apply(delta(size="0", best_ask="0.6"), utcnow())
    assert state.book(market).yes_asks[0].price == Decimal("0.6")
    state.apply(delta(price="0.4", size="3.25", best_ask="0.4"), utcnow())
    assert state.book(market).yes_asks[0].size == Decimal("3.25")


def test_bids_are_not_asks_and_trade_events_do_not_refresh_quotes(market):
    state = seeded(market)
    state.apply(delta(side="BUY", price="0.4", best_bid="0.4"), utcnow())
    book = state.book(market)
    assert book.yes_asks[0].price == Decimal("0.5")
    assert not state.apply({"event_type": "last_trade_price", "price": "0.9"}, utcnow())
    assert state.book(market).id == book.id


@pytest.mark.parametrize(
    "fields",
    [
        {"size": "-1"},
        {"price": "NaN"},
        {"price": "1.1"},
        {"side": "UNKNOWN"},
        {"best_ask": "0.55"},
        {"side": "BUY", "price": "0.6", "best_bid": "0.6"},
    ],
)
def test_bad_delta_does_not_partially_modify_book(market, fields):
    state = seeded(market)
    before = state.book(market).id
    with pytest.raises(StreamIntegrityError):
        state.apply(delta(**fields), utcnow())
    assert state.book(market).id == before


def test_missing_snapshot_wrong_identity_and_out_of_order_fail_closed(market):
    state = MarketBooks([market])
    with pytest.raises(StreamIntegrityError):
        state.apply(delta(), utcnow())
    with pytest.raises(StreamNotReady):
        state.book(market)
    state = seeded(market)
    for event in [
        {**delta(), "market": "other-condition"},
        delta(now=utcnow() - timedelta(seconds=5)),
        delta(now=utcnow() + timedelta(minutes=1)),
    ]:
        with pytest.raises(StreamIntegrityError):
            state.apply(event, utcnow())


def test_new_snapshot_replaces_depth_and_old_other_outcome_is_not_refreshed(market):
    state = seeded(market)
    now = utcnow()
    event = snapshot(now=now)
    event["asks"] = [{"price": "0.7", "size": "8"}]
    state.apply(event, now)
    assert len(state.book(market).yes_asks) == 1
    future_receipt = now + timedelta(seconds=20)
    state.apply(snapshot(now=future_receipt), future_receipt)
    with pytest.raises(StreamNotReady, match="synchronized"):
        state.book(market)


async def test_session_subscribes_handles_array_frames_heartbeat_and_cleanup(market, monkeypatch):
    stream = PolymarketStream(heartbeat_seconds=0.02)
    sent = []
    queue = asyncio.Queue()
    processed = asyncio.Event()
    now = utcnow()
    await queue.put(json.dumps([snapshot("yes", now), snapshot("no", now)]))
    await queue.put(json.dumps(delta(now=now)))

    class Socket:
        async def send(self, text):
            sent.append(text)
            if text == "PING":
                await queue.put("PONG")

        async def recv(self):
            if stream.price_changes and "PING" in sent:
                processed.set()
            return await queue.get()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("arbbot.streams.polymarket.connect", lambda *a, **k: Socket())
    await stream.subscribe([market])
    try:
        await asyncio.wait_for(processed.wait(), 1)
        assert json.loads(sent[0]) == {"assets_ids": ["no", "yes"], "type": "market"}
        assert stream.book(market).yes_asks[0].size == Decimal("7.125")
        task = stream.task
        await stream.subscribe([market])
        assert stream.task is task
    finally:
        await stream.aclose()
    assert stream.task is None
    assert not stream.state.books
    with pytest.raises(StreamNotReady):
        stream.book(market)


async def test_connection_loss_discards_depth_and_reconnect_waits_for_snapshot(market, monkeypatch):
    stream = PolymarketStream()
    attempts = 0
    failed = asyncio.Event()
    reconnect = asyncio.Event()

    async def session():
        nonlocal attempts
        attempts += 1
        stream.connected = True
        if attempts == 1:
            now = utcnow()
            stream.state.apply(snapshot("yes", now), now)
            stream.state.apply(snapshot("no", now), now)
            raise OSError("lost connection")
        reconnect.set()
        await asyncio.Future()

    async def backoff(delay):
        assert delay >= 1
        assert not stream.connected
        assert not stream.state.books
        failed.set()

    monkeypatch.setattr(stream, "session", session)
    monkeypatch.setattr("arbbot.streams.polymarket.asyncio.sleep", backoff)
    await stream.subscribe([market])
    try:
        await asyncio.wait_for(reconnect.wait(), 1)
        assert failed.is_set()
        with pytest.raises(StreamNotReady):
            stream.book(market)
    finally:
        await stream.aclose()


async def test_stream_book_flows_through_pipeline_storage_and_health(database, market):
    from arbbot.ingestion.pipeline import Pipeline

    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live"})
    stream = PolymarketStream()
    stream.state = seeded(market)
    stream.connected = True
    stream.state.apply(delta(), utcnow())
    adapter = StreamingPolymarketAdapter(None, stream=stream)

    async def discover(limit):
        return [market]

    adapter.discover = discover
    pipeline = Pipeline(settings, repository, [adapter])
    await pipeline.cycle()
    persisted = await repository.book("live", market.id)
    assert persisted.yes_asks[0].size == Decimal("7.125")
    assert persisted.raw["yes"]["last_event"]["event_type"] == "price_change"
    assert (await repository.health("live", 120))[0]["fresh_book_count"] == 1
    stream.connected = False
    await pipeline.cycle()
    health = (await repository.health("live", 120))[0]
    assert health["fresh_book_count"] == 0
    assert health["error"] == "StreamNotReady"


async def test_missing_pong_terminates_session(market, monkeypatch):
    stream = PolymarketStream(heartbeat_seconds=0.01)
    stream.state = MarketBooks([market])

    class SilentSocket:
        async def send(self, text):
            pass

        async def recv(self):
            await asyncio.Future()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("arbbot.streams.polymarket.connect", lambda *a, **k: SilentSocket())
    with pytest.raises(ExceptionGroup) as error:
        await asyncio.wait_for(stream.session(), 1)
    assert isinstance(error.value.exceptions[0], TimeoutError)


async def test_changed_subscriptions_drop_old_generation(market, monkeypatch):
    stream = PolymarketStream()
    started = asyncio.Event()

    async def run():
        started.set()
        await asyncio.Future()

    monkeypatch.setattr(stream, "run", run)
    await stream.subscribe([market])
    await started.wait()
    original = stream.task
    stream.state = seeded(market)
    replacement = market.model_copy(update={"tokens": {"yes": "new-yes", "no": "new-no"}})
    try:
        await stream.subscribe([replacement])
        assert original.cancelled()
        assert not stream.state.books
        assert set(stream.state.tokens) == {"new-yes", "new-no"}
        await stream.subscribe([])
        assert stream.task is None
    finally:
        await stream.aclose()


async def test_periodic_resubscription_clears_prior_depth(market, monkeypatch):
    stream = PolymarketStream(resync_seconds=0.01)
    expired = asyncio.Event()

    async def session():
        stream.connected = True
        stream.state = seeded(market)
        await asyncio.Future()

    async def backoff(delay):
        assert not stream.connected
        assert not stream.state.books
        expired.set()
        await asyncio.Future()

    monkeypatch.setattr(stream, "session", session)
    monkeypatch.setattr("arbbot.streams.polymarket.asyncio.sleep", backoff)
    await stream.subscribe([market])
    try:
        await asyncio.wait_for(expired.wait(), 1)
    finally:
        await stream.aclose()
