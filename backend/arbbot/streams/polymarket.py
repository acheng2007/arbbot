"""Polymarket market-channel snapshots and absolute price-level updates."""

import asyncio
import json
import logging
import random
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from websockets.asyncio.client import connect

from arbbot.domain import Book, Level, Market, utcnow
from arbbot.exchanges.polymarket import PolymarketAdapter

URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
logger = logging.getLogger(__name__)


class StreamNotReady(Exception):
    """No synchronized snapshot is available on the current connection."""


class StreamIntegrityError(Exception):
    """Discard the connection's state and request new snapshots."""


def amount(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise StreamIntegrityError("Invalid amount")
    return result


def price(value):
    result = amount(value)
    if result > 1:
        raise StreamIntegrityError("Invalid price")
    return result


@dataclass
class TokenBook:
    bids: dict[Decimal, Decimal]
    asks: dict[Decimal, Decimal]
    source_at: datetime
    received_at: datetime
    event: dict


class MarketBooks:
    """Pure reducer. No delta is usable before its token's full snapshot."""

    def __init__(self, markets: list[Market]):
        self.markets = {market.id: market for market in markets}
        self.tokens = {token: market for market in markets for token in market.tokens.values()}
        self.books: dict[str, TokenBook] = {}

    def apply(self, event: dict, received_at: datetime) -> bool:
        kind = event.get("event_type")
        if kind not in {"book", "price_change"}:
            return False
        source_at = datetime.fromtimestamp(int(event["timestamp"]) / 1000, UTC)
        if source_at > received_at + timedelta(seconds=2):
            raise StreamIntegrityError("Future event")
        changes = [event] if kind == "book" else event["price_changes"]
        pending = {}
        for change in changes:
            token = change["asset_id"]
            market = self.tokens.get(token)
            if market is None:
                continue
            if event["market"] != market.raw.get("conditionId"):
                raise StreamIntegrityError("Condition identity mismatch")
            previous = pending.get(token) or self.books.get(token)
            if previous and source_at < previous.source_at:
                raise StreamIntegrityError("Out-of-order event")
            if previous and previous.event == event and token not in pending:
                continue
            if kind == "book":

                def levels(name):
                    result = {}
                    for entry in event[name]:
                        p, size = price(entry["price"]), amount(entry["size"])
                        if p in result:
                            raise StreamIntegrityError("Duplicate snapshot level")
                        if size:
                            result[p] = size
                    return result

                current = TokenBook(levels("bids"), levels("asks"), source_at, received_at, event)
            else:
                if previous is None:
                    raise StreamIntegrityError("Delta before snapshot")
                current = replace(previous, bids=previous.bids.copy(), asks=previous.asks.copy())
                if change["side"] not in {"BUY", "SELL"}:
                    raise StreamIntegrityError("Invalid side")
                side = current.bids if change["side"] == "BUY" else current.asks
                p, size = price(change["price"]), amount(change["size"])
                if size:
                    side[p] = size
                else:
                    side.pop(p, None)
                current.source_at, current.received_at, current.event = (
                    source_at,
                    received_at,
                    event,
                )
            pending[token] = current
        # Validate after the entire batch: multiple changes can affect one token.
        for change in changes:
            current = pending.get(change["asset_id"])
            if current is None:
                continue
            if current.bids and current.asks and max(current.bids) >= min(current.asks):
                raise StreamIntegrityError("Crossed book")
            if kind == "price_change":
                for field, levels, best, empty in (
                    ("best_bid", current.bids, max, Decimal(0)),
                    ("best_ask", current.asks, min, Decimal(1)),
                ):
                    if change.get(field) is not None:
                        expected = best(levels) if levels else empty
                        if price(change[field]) != expected:
                            raise StreamIntegrityError("Top-of-book mismatch")
        self.books.update(pending)
        return bool(pending)

    def book(self, market: Market) -> Book:
        try:
            yes, no = (self.books[market.tokens[side]] for side in ("yes", "no"))
        except KeyError as exc:
            raise StreamNotReady from exc
        if abs((yes.source_at - no.source_at).total_seconds()) > 10:
            raise StreamNotReady("Outcome timestamps are not synchronized")

        def asks(token):
            return tuple(Level(price=p, size=q) for p, q in sorted(token.asks.items()))

        def evidence(token):
            return {
                "bids": [{"price": str(p), "size": str(q)} for p, q in sorted(token.bids.items())],
                "asks": [{"price": str(p), "size": str(q)} for p, q in sorted(token.asks.items())],
                "source_at": token.source_at.isoformat(),
                "received_at": token.received_at.isoformat(),
                "last_event": token.event,
            }

        return Book(
            market_id=market.id,
            mode=market.mode,
            yes_asks=asks(yes),
            no_asks=asks(no),
            min_order_size=market.raw["orderMinSize"],
            source_at=min(yes.source_at, no.source_at),
            received_at=max(yes.received_at, no.received_at),
            raw={"transport": "websocket", "url": URL, "yes": evidence(yes), "no": evidence(no)},
        )


class PolymarketStream:
    def __init__(self, *, url=URL, heartbeat_seconds=10, resync_seconds=300):
        self.url = url
        self.heartbeat_seconds = heartbeat_seconds
        self.resync_seconds = resync_seconds
        self.state = MarketBooks([])
        self.connected = False
        self.task = None
        self.price_changes = 0

    async def subscribe(self, markets: list[Market]):
        next_state = MarketBooks(markets)

        # A changed condition or token mapping requires a new subscription generation.
        def identity(state):
            return {
                token: (market.id, market.raw.get("conditionId"))
                for token, market in state.tokens.items()
            }

        if identity(next_state) == identity(self.state) and self.task and not self.task.done():
            return
        await self.aclose()
        self.state = next_state
        if self.state.tokens:
            self.task = asyncio.create_task(self.run(), name="polymarket-market-stream")

    async def aclose(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        self.connected = False
        self.state.books.clear()

    def book(self, market):
        if not self.connected:
            raise StreamNotReady("Stream disconnected")
        return self.state.book(market)

    async def session(self):
        async with connect(
            self.url,
            ping_interval=None,
            open_timeout=10,
            close_timeout=5,
            max_size=8 * 1024 * 1024,
            max_queue=32,
        ) as socket:
            await socket.send(
                json.dumps({"assets_ids": sorted(self.state.tokens), "type": "market"})
            )
            self.connected = True
            logger.info("polymarket_stream_connected", extra={"venue": "polymarket"})
            loop = asyncio.get_running_loop()
            last_pong = loop.time()

            async def heartbeat():
                while True:
                    await socket.send("PING")
                    await asyncio.sleep(self.heartbeat_seconds)
                    if loop.time() - last_pong > self.heartbeat_seconds * 3:
                        raise TimeoutError("Polymarket heartbeat missed")

            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(heartbeat())
                while True:
                    frame = await socket.recv()
                    if frame == "PONG":
                        last_pong = loop.time()
                        continue
                    payload = json.loads(frame, parse_float=str)
                    for event in payload if isinstance(payload, list) else [payload]:
                        changed = self.state.apply(event, utcnow())
                        if changed and event.get("event_type") == "price_change":
                            self.price_changes += 1
                            if self.price_changes == 1 or self.price_changes % 100 == 0:
                                logger.info(
                                    "polymarket_price_change", extra={"venue": "polymarket"}
                                )

    async def run(self):
        delay = 1
        while True:
            started = asyncio.get_running_loop().time()
            try:
                # Periodic fresh subscriptions bound drift where no sequence number exists.
                async with asyncio.timeout(self.resync_seconds):
                    await self.session()
            except Exception as exc:
                while isinstance(exc, BaseExceptionGroup):
                    exc = exc.exceptions[0]
                error = type(exc).__name__
                if isinstance(exc, StreamIntegrityError):
                    error += ": " + str(exc)
                logger.warning(
                    "polymarket_stream_resync",
                    extra={"venue": "polymarket", "error": error},
                )
            finally:
                self.connected = False
                self.state.books.clear()
            if asyncio.get_running_loop().time() - started > 30:
                delay = 1
            await asyncio.sleep(delay + random.uniform(0, delay / 4))
            delay = min(delay * 2, 30)


class StreamingPolymarketAdapter(PolymarketAdapter):
    def __init__(self, http, market_ids=None, *, stream=None):
        super().__init__(http, market_ids)
        self.stream = stream or PolymarketStream()

    async def discover(self, limit):
        markets = await super().discover(limit)
        await self.stream.subscribe(markets)
        return markets

    async def fetch_book(self, market):
        return self.stream.book(market)

    async def aclose(self):
        await self.stream.aclose()
