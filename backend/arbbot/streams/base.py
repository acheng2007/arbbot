from collections import OrderedDict
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from arbbot.domain import Book, Level, Market, digest
from arbbot.quality import book_issue
from arbbot.streams.models import Disconnected, Snapshot, StreamEvent

EVENT_ADAPTER = TypeAdapter(StreamEvent)


class BookStream(Protocol):
    def events(self) -> AsyncIterator[StreamEvent]: ...

    async def request_snapshot(self, market: Market, epoch: str) -> None:
        """Request an authoritative snapshot in the specified active subscription epoch."""
        ...

    async def close(self) -> None: ...


class BookState:
    """One market, mode, and subscription epoch. Consumers use eligible_book only."""

    def __init__(
        self,
        market: Market,
        *,
        max_buffer=128,
        max_buffer_bytes=2097152,
        max_event_bytes=1048576,
        max_levels=10000,
    ):
        if min(max_buffer, max_buffer_bytes, max_event_bytes, max_levels) < 1:
            raise ValueError("Stream bounds must be positive")
        self.market = market
        self.max_buffer, self.max_buffer_bytes = max_buffer, max_buffer_bytes
        self.max_event_bytes, self.max_levels = max_event_bytes, max_levels
        self.epoch = None
        self.status = "disconnected"
        self.reason = "not_connected"
        self.sequence = None
        self._book = None
        self._pending = {}
        self._pending_bytes = 0
        self._seen = OrderedDict()
        self._snapshot_floor = -1
        self._last_source = None
        self._last_received = None

    def connect(self, epoch: str):
        if not isinstance(epoch, str) or not 1 <= len(epoch) <= 128 or epoch == self.epoch:
            raise ValueError("Reconnect requires a new nonempty subscription epoch")
        self.epoch = epoch
        self.invalidate("snapshot_required")
        self._snapshot_floor = -1
        self._last_source = self._last_received = None

    def invalidate(self, reason: str):
        self._snapshot_floor = max(self._snapshot_floor, self.sequence or 0, *self._pending.keys())
        self.status, self.reason = "resync_required", reason
        self.sequence, self._book = None, None
        self._pending.clear()
        self._pending_bytes = 0
        self._seen.clear()

    def eligible_book(self, now: datetime, max_age_seconds: int) -> Book | None:
        if now.tzinfo is None or max_age_seconds <= 0:
            raise ValueError("Eligibility requires an aware time and positive freshness bound")
        if self.status != "synchronized" or self.market.status != "open":
            return None
        if book_issue(self.market, self._book, now, max_age_seconds):
            return None
        # Book contains mutable raw metadata; do not expose the state's owned copy.
        return self._book.model_copy(deep=True)

    @staticmethod
    def fingerprint(event):
        payload = event.model_dump(mode="json")
        if isinstance(event, Snapshot):
            payload["book"].pop("received_at")
        else:
            payload.pop("received_at")
        return digest(payload)

    def remember(self, event):
        self._seen[event.sequence] = self.fingerprint(event)
        while len(self._seen) > self.max_buffer:
            self._seen.popitem(last=False)

    def buffer(self, event, size):
        previous = self._pending.get(event.sequence)
        if previous:
            if self.fingerprint(previous) != self.fingerprint(event):
                self.invalidate("conflicting_duplicate")
                return "resync_required"
            return "duplicate"
        if (
            len(self._pending) >= self.max_buffer
            or self._pending_bytes + size > self.max_buffer_bytes
        ):
            self._snapshot_floor = max(self._snapshot_floor, event.sequence)
            self.invalidate("buffer_overflow")
            return "resync_required"
        self._pending[event.sequence] = event
        self._pending_bytes += size
        return "buffered"

    def apply_delta(self, event, *, replay=False):
        old = self._book
        if event.previous_sequence != self.sequence:
            self.invalidate("sequence_gap")
            return False
        if (not replay and event.received_at < old.received_at) or (
            old.source_at and event.source_at and event.source_at < old.source_at
        ):
            self._snapshot_floor = max(self._snapshot_floor, event.sequence)
            self.invalidate("timestamp_regression")
            return False
        levels = {
            "yes": {v.price: v.size for v in old.yes_asks},
            "no": {v.price: v.size for v in old.no_asks},
        }
        for change in event.changes:
            if change.size == 0:
                levels[change.outcome].pop(change.price, None)
            else:
                levels[change.outcome][change.price] = change.size
        if sum(len(side) for side in levels.values()) > self.max_levels:
            self._snapshot_floor = max(self._snapshot_floor, event.sequence)
            self.invalidate("level_overflow")
            return False
        self._book = Book(
            market_id=old.market_id,
            mode=old.mode,
            yes_asks=tuple(Level(price=p, size=q) for p, q in sorted(levels["yes"].items())),
            no_asks=tuple(Level(price=p, size=q) for p, q in sorted(levels["no"].items())),
            min_order_size=old.min_order_size,
            source_at=event.source_at if event.source_at is not None else old.source_at,
            received_at=max(event.received_at, old.received_at),
            raw={
                "stream_epoch": event.epoch,
                "sequence": event.sequence,
                "previous_book_id": old.id,
                "event": event.raw,
            },
        )
        self.sequence = event.sequence
        self._last_source = self._book.source_at
        self._last_received = self._book.received_at
        self.remember(event)
        return True

    def accept(self, event: StreamEvent) -> str:
        # Revalidate nested models and detach mutable payloads at the trust boundary.
        try:
            encoded = event.model_dump_json()
            size = len(encoded.encode())
            if size > self.max_event_bytes:
                self.invalidate("event_overflow")
                # The discarded event has no trusted sequence boundary. A snapshot
                # from this subscription cannot prove that it covers the lost update.
                self.status = "disconnected"
                return "resync_required"
            event = EVENT_ADAPTER.validate_json(encoded)
        except (ValidationError, ValueError, TypeError, AttributeError):
            self.invalidate("invalid_event")
            self.status = "disconnected"
            return "resync_required"
        if event.epoch != self.epoch or self.status == "disconnected":
            return "ignored_epoch"
        if isinstance(event, Disconnected):
            self.invalidate(event.reason)
            self.status = "disconnected"
            return "disconnected"
        identity = event.book if isinstance(event, Snapshot) else event
        if identity.market_id != self.market.id or identity.mode != self.market.mode:
            self.invalidate("identity_mismatch")
            return "resync_required"
        if event.sequence in self._seen:
            if self._seen[event.sequence] == self.fingerprint(event):
                return "duplicate"
            self.invalidate("conflicting_duplicate")
            return "resync_required"
        if self.sequence is not None and event.sequence < self.sequence:
            return "out_of_order"
        if isinstance(event, Snapshot):
            if event.sequence < self._snapshot_floor:
                return "out_of_order"
            if (self._last_received and event.book.received_at < self._last_received) or (
                self._last_source
                and event.book.source_at
                and event.book.source_at < self._last_source
            ):
                self.invalidate("timestamp_regression")
                return "resync_required"
            if len(event.book.yes_asks) + len(event.book.no_asks) > self.max_levels:
                self.invalidate("level_overflow")
                return "resync_required"
            pending = sorted(self._pending.values(), key=lambda delta: delta.sequence)
            self._pending.clear()
            self._pending_bytes = 0
            self._seen.clear()
            self._book, self.sequence = event.book, event.sequence
            self._last_source = event.book.source_at
            self._last_received = event.book.received_at
            self.remember(event)
            for delta in pending:
                if delta.sequence > self.sequence and not self.apply_delta(delta, replay=True):
                    self._snapshot_floor = max(self._snapshot_floor, *(d.sequence for d in pending))
                    return "resync_required"
            self.status, self.reason = "synchronized", None
            return "synchronized"
        if self.status != "synchronized":
            return self.buffer(event, size)
        if event.previous_sequence != self.sequence:
            self.invalidate("sequence_gap")
            self.buffer(event, size)
            return "resync_required"
        if not self.apply_delta(event):
            return "resync_required"
        return "applied"
