> Historical snapshot retained during the October 11, 2026 reconciliation.
> Branches, pending states, test counts, and next actions below describe earlier sessions.
> Use the [current handoff](../live-data-handoff.md) and [roadmap](../../implementation-roadmap.md) for active work.

# Live data handoff

## Polymarket WebSocket integration

Branch: `demo/live-prices`.
No PR was opened or merged for this change.
The user requested connection to the live Polymarket WebSocket and listening for `price_change` events.

Implemented the public `/ws/market` subscription for all discovered YES/NO tokens, initial snapshots, absolute price-level changes, zero-size removal, Decimal depth, and source/receipt timestamps.
The persistent listener sends application heartbeats, retries with bounded backoff, discards disconnected state, validates identity/timestamps/top-of-book consistency, and periodically resubscribes for fresh snapshots.
The continuous worker now uses this adapter by default for Polymarket, while Kalshi stays on REST.
The existing pipeline persists reconstructed stream snapshots and evaluates them on its normal cycle.
`--once` and the explicit `ARBBOT_POLYMARKET_WEBSOCKET=false` configuration retain REST behavior.
Runtime and development dependencies pin `websockets==17.1`.

Live verification confirmed initial `book` frames and subsequent `price_change` batches for real tokens.
The running demo API returned `raw.transport=websocket` and `raw.yes.last_event.event_type=price_change` for `polymarket:559651`.
The demo remains at <http://localhost:3000/markets?venue=polymarket>, using the isolated `arbbot-demo` Compose project.

Validation: Ruff lint/format checks passed, all 91 backend tests passed against PostgreSQL in isolated schemas, and all 16 stream-focused tests passed locally.
The full SQLite suite passed with 88 tests before the final three lifecycle tests were added and validated in the focused and PostgreSQL runs.
The Docker API/worker build and deployment passed.
The live browser smoke test passed for both venues on desktop and mobile, requiring Polymarket WebSocket provenance and at least two distinct persisted snapshots per detail page.
The rendered desktop quote screen was visually inspected.
The final worker logs confirmed an active stream and continuing `price_change` events after deployment.
Some inactive or older books remain excluded as `book_stale` or `out_of_order_snapshot`; no freshness checks were weakened.
No blocking issue remains for the requested stream connection.

No sequence numbers are documented in this feed.
Periodic snapshots and best-price validation bound drift but cannot prove that every change was received.
The worker persists cycle snapshots, not every intermediate delta, and the browser refreshes prices every five seconds.
No live settlement equivalence was approved and no trading was enabled.

Next action: add an event-driven publication path and market-price SSE updates so WebSocket changes reach the browser without waiting for the ingestion cycle and five-second browser refresh.
Preserve immutable quote timestamps, disconnected-feed invalidation, and the isolated demo database when doing so.
