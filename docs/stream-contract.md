# Order-book stream contract

`arbbot.streams.models` defines exchange-neutral snapshots, absolute level replacements, and disconnect events.
`BookStream` describes the asynchronous adapter interface; `BookState` owns one market, mode, and subscription epoch.
This contract does not open sockets or change the current REST ingestion worker.
Venue implementations follow in issues #28 and #29, with worker integration in #30.

## Adapter responsibilities

Create a fresh epoch for each subscription and call `connect(epoch)` before delivering events.
Never reuse epoch identifiers, including after an intervening subscription.
Attach the same epoch to snapshots, deltas, and disconnects from that subscription.
Preserve source timestamps separately from receipt timestamps; do not fabricate source timestamps.
Normalize changes into absolute quantities at each outcome/price, using zero to delete a level.
Aggregate duplicate changes before emitting an event.
Normalize venue-specific bid/complement representations into the existing `Book` ask-side representation.

Each delta identifies its sequence and the predecessor sequence for this market's normalized state.
The adapter must establish continuity from the venue's documented sequence or integrity guarantees before asserting this predecessor.
A shared-channel sequence need not advance by one for a particular market.
Do not manufacture continuity by numbering messages in local arrival order when the source cannot establish it.
When continuity cannot be established, request an authoritative snapshot or disconnect and resubscribe.
Do not emit empty heartbeat deltas to refresh quote timestamps.
Reject oversized wire messages before decoding; the normalized event bound is an additional defense, not a transport memory limit.

## State and recovery

Only `eligible_book(now, max_age_seconds)` exposes a book to consumers.
It returns a detached copy only when synchronized, the market is open, and the existing quote freshness/identity rules pass.
Disconnected, incomplete, future-dated, and stale books are ineligible.
Preserve downstream invalidation when wiring this contract into the worker; retaining an older published opportunity would defeat these guarantees.

| Input | Behavior |
| --- | --- |
| Initial or reconnect snapshot | Replace the normalized book exactly, including original metadata and timestamps. |
| Contiguous delta | Atomically replace/delete levels with exact decimal values. |
| Known duplicate | Ignore without refreshing receipt time. |
| Conflicting duplicate | Invalidate and require a covering snapshot. |
| Older sequence | Ignore without refreshing quotes. |
| Gap | Invalidate, buffer the delta, and request a snapshot. |
| Pre-snapshot deltas | Buffer, then replay in sequence order after discarding updates covered by the snapshot. |
| Buffer overflow or failed replay | Require a snapshot covering all discarded sequences. |
| Invalid or oversized event | Disconnect logically; require a new subscription because the discarded sequence cannot be trusted. |
| Disconnect | Clear eligibility and reject subsequent events from that subscription. |
| Different epoch | Ignore valid late events from that epoch. |

Inspect both `status` and `reason` after `accept` returns `resync_required`.
If status is `disconnected`, resubscribe with a fresh epoch; otherwise request a covering snapshot in the existing epoch.
Defaults bound pending events to 128 and 2 MiB, each normalized event to 1 MiB, and the combined book to 10,000 levels.
Recent duplicate fingerprints are bounded by the pending-event count setting.
Oversized or invalid messages fail closed even if their claimed epoch differs, since their identity has not passed validation.

Source and receipt timestamp regressions invalidate live deltas.
Buffered deltas may precede the snapshot's receipt time; replay preserves the later receipt timestamp.
A delta missing a source timestamp retains the previous source timestamp rather than making older source data appear fresh.
Adapters must provide timely snapshots or trusted source timestamps to recover freshness.

## Validation

`backend/tests/test_stream_contract.py` exercises exact snapshot reconstruction, atomic updates, deletion, duplicates, gaps, replay, overflow, timestamp regressions, subscription changes, invalid nested models, and eligibility.
These are deterministic stream-boundary tests, not live exchange or worker end-to-end tests.
