# Backend behavior and operations

## Automatic live qualification

Live discovery now uses evidence-based automatic qualification by default, without required human reviews or account setup.
Qualified conditional estimates and separate potential price gaps are available through the API.
See [automatic qualification](automatic-qualification.md) for current source-language coverage, public fee/account assumptions, extension interfaces, and the recorded worker/API acceptance command.
The [system design](system-design.md) and [roadmap](implementation-roadmap.md) define the current runtime boundaries and delivery priorities.
Historical review-file, approval, and access-profile instructions below apply to the optional path selected with `ARBBOT_AUTOMATIC_QUALIFICATION=false`; they do not gate default automatic discovery.

## Ingestion

The worker discovers a bounded set of markets, polls Kalshi REST order books, consumes Polymarket WebSocket books, persists normalized results, discovers candidates, evaluates verified pairs, and publishes a coherent opportunity view.
Exchange requests use bounded concurrency, pacing, timeouts, and retries for transport errors, rate limits, and selected server failures.
Kalshi reads complete REST snapshots each cycle.
Polymarket keeps full snapshots plus absolute price-level changes in memory and publishes the latest complete state each cycle.
Kalshi WebSocket ingestion is not implemented yet.

### Polymarket WebSocket

Continuous live workers connect to `wss://ws-subscriptions-clob.polymarket.com/ws/market` by default.
Gamma REST discovery supplies condition IDs, YES/NO token IDs, and minimum order sizes.
The public subscription is `{"assets_ids":["TOKEN_ID"],"type":"market"}` and requires no credentials.
The listener consumes initial `book` snapshots and `price_change` batches, replacing the specified price level with its new absolute size or removing it when size is zero.
BUY updates affect bids, SELL updates affect asks, and last-trade events never substitute for executable depth.

Text `PING` frames are sent every ten seconds, and missing `PONG` replies terminate the connection after thirty seconds.
Disconnects, malformed frames, identity mismatches, out-of-order timestamps, crossed books, and inconsistent best prices discard the in-memory books and trigger reconnection with capped exponential backoff and jitter.
Subscription changes also clear the old generation.
New deltas cannot be applied until a full snapshot for their token arrives.
Full resubscription every five minutes bounds drift; the documented feed has no sequence number, so detecting every lost update is not guaranteed and the venue hash is retained as provenance rather than treated as a verified checksum.

The existing worker cycle persists and evaluates the latest stream state, so this is continuous exchange ingestion with cycle-based publication, not per-event database writes.
Stored snapshots retain reconstructed depth, per-outcome source/receipt times, and each outcome's latest raw event under `raw`, with `transport: websocket`.
Intermediate deltas between worker cycles are not individually journaled.
The 30-second default quote age and 10-second outcome skew checks still apply; heartbeats do not make old prices fresh.
An unavailable stream yields `StreamNotReady` in ingestion health on the next cycle and blocks affected evaluations.
Previously persisted books remain accessible for inspection with their original timestamps.

Set `ARBBOT_POLYMARKET_WEBSOCKET=false` explicitly to use REST polling instead.
The `--once` worker always uses REST snapshots because a one-cycle process cannot maintain a persistent stream.
API status describes the configured continuous-worker transport.
The browser still refreshes price queries every five seconds; opportunity updates use the existing SSE connection.

Protocol verified against [Polymarket's official real-time data documentation](https://docs.polymarket.com/market-data/realtime-data) and live public messages on September 23, 2026.

The default discovery limit is 50 supported markets per exchange, with at most 20 discovery pages per cycle.
This is a monitored sample, not exhaustive exchange coverage.
Explicit watchlists replace broad discovery and should be used for reviewed pairs.
The polling interval is a pause after each completed cycle, not a guaranteed quote latency.

Kalshi fixed-point bids are converted to complementary asks.
Polymarket token IDs are associated by outcome name, and both token books are fetched.
Negative-risk markets, nonbinary markets, and non-unit Kalshi payouts are excluded.
Raw payloads are retained, calculations use `Decimal`, and API monetary values are decimal strings.

Kalshi snapshots have no source timestamp in the implemented response format, so the backend reports this and measures age from receipt.
Polymarket snapshots retain source timestamps and reject mismatched token identities or unsynchronized outcome books.
Out-of-order snapshots never replace the latest stored book.
Identical snapshot replays are idempotent.

## Live mode

For local Python processes, configure the root `.env` file:

```dotenv
ARBBOT_MODE=live
ARBBOT_DISCOVERY_LIMIT=50
ARBBOT_KALSHI_TICKERS=["EXACT-KALSHI-TICKER"]
ARBBOT_POLYMARKET_MARKET_IDS=["EXACT-GAMMA-MARKET-ID"]
ARBBOT_REVIEWS_FILE=/absolute/path/to/reviews.json
```

Omit watchlists to use paginated discovery.
Automatic mode does not require a review file; it can publish qualified estimates only when complete supported evidence and financial inputs are available.
With automatic qualification disabled, omitting reviews leaves discovery operational but cannot supply settlement approval.
Use a separate database for production and simulation even though queries isolate modes.

The Kalshi adapter supports optional RSA signing through `ARBBOT_KALSHI_KEY_ID` and `ARBBOT_KALSHI_PRIVATE_KEY_PATH`.
Keys stay in local files and are never returned through the API.
Kalshi's public tutorial and authenticated endpoint reference differ on authentication requirements; configure a key if public reads are rejected.
Authentication failures appear in exchange health rather than triggering a simulation fallback.

For the public live-price demo, run `docker compose -p arbbot-demo --env-file infra/demo.env up --build -d`.
This starts the web app, live API, worker, and an isolated PostgreSQL volume, with database port 55433.
For custom watchlists or reviewed pairs, use a local Compose override, pass worker configuration explicitly, and mount credentials and review files read-only.
Do not put secrets in images or source control.
No adapter places orders or accesses account balances.

## Settlement source evidence

Settlement rules often depend on documents published outside the exchanges, so every retrieval attempt is persisted as an immutable source artifact.
An artifact records the venue, market, document URL, evidence label, media type, exact bytes, SHA-256 content digest, source timestamp, and receipt timestamp.
Artifact identifiers are derived from the captured content, so repeating an identical capture records another observation of the same artifact instead of a duplicate row.
A changed document therefore produces a new artifact and leaves the earlier bytes readable for audit.
Each artifact also stores the market terms hash that was current when the evidence was captured, so later terms changes can invalidate the reviews that relied on it.

Failed retrievals are stored with the same provenance and an explicit reason, keeping missing evidence visible instead of silently absent.
`SourceRepository.missing_evidence` reports labels that were never captured, whose most recent observation failed, or whose evidence predates a supplied terms hash.
Stored documents are bounded by `ARBBOT_SOURCE_MAX_BYTES`, which defaults to 1 MB and cannot exceed the 5 MB ceiling in `arbbot.sources.models`.
An oversized document is recorded as a `too_large` failure rather than truncated or dropped.

This storage layer does not fetch anything.
Venue-specific evidence collection and any API exposure are separate tasks.

## Settlement review

Normalized title similarity and nearby closing dates produce candidates only.
The matcher supports a bounded monitored set and does not claim semantic equivalence or exhaustive cross-exchange coverage.

A review file is a JSON array of `Review` objects.
Export the exact schema with:

```sh
.venv/bin/python -m arbbot.api.export_schema --reviews --output docs/reviews.schema.json
```

Each review requires:

- Both market IDs and current `terms_hash` values from the markets API.
- A verified or rejected decision, reviewer, rationale, and expiry.
- Evidence covering resolution sources, deadlines, time zones, cancellation, and exceptional settlement.
- A scenario matrix including ordinary YES/YES and NO/NO outcomes and every relevant exceptional combination.
- A cost policy per venue specifying fee bounds, minimum sizes and notionals, and currency conversion bounds.

Scenario values represent YES payouts per contract, with NO payouts complementary to one.
Reject markets with refunds or settlement behavior this model cannot represent.
The reviewer is responsible for scenario completeness; the evaluator cannot establish completeness from free text.

Fees are reviewed upper bounds per contract plus a fixed allowance per leg, denominated in the venue's settlement asset.
Bounds must cover taker fees, rounding, and other applicable costs over the intended size range.
The evidence field should record sources, effective dates, size limits, and the bound's rationale.
Dynamic fee schedules are not yet automatically retrieved and validated.
Live evaluation always requires an explicit cost policy, including any intentional zero-fee assumption.

USD valuation uses a cost conversion ceiling and payout conversion floor for each venue.
Do not treat Polymarket collateral and cash USD as interchangeable without reviewing conversion costs and risks.
Current official documentation uses both pUSD and USDC terminology, so verify actual collateral before approving a policy.
Unresolved collateral, fee, or settlement ambiguity must leave a pair unverified.

Reviews reload each cycle, and changed terms or expired reviews invalidate verification.
Malformed or duplicate entries fail the cycle and suppress current opportunities.
Historical results embed reviews, reference exact book snapshots, and retain versioned settlement metadata.

## Evaluation

The engine tests buying YES on one venue and NO on the other in both directions.
It checks every whole-contract quantity within configured depth, size, minimum-order, and capital constraints and selects the highest estimated net profit per direction.
Fractional depth may contribute to fills, but order quantities are restricted to whole contracts.

Estimated outlay includes depth-weighted cost, rounded-up fee bounds, and a configurable slippage reserve.
Capital required funds full orders at their limit prices plus fee and slippage allowances.
Minimum scenario payout minus estimated outlay determines estimated net profit.
Slippage reserves are cost allowances and do not guarantee fills.

Closed markets, missing or stale books, future timestamps, mixed modes, excessive quote skew, and invalid reviews block evaluation.
Individual book failures suppress only opportunities using the affected market.
Fresh books from other markets remain eligible even when the exchange's aggregate health is degraded.
Discovery failures, missing catalogs, and stale worker heartbeats still suppress opportunities using that venue.
The API filters current results against the exact healthy book snapshots before pagination, so recovery requires a new evaluation and cannot revive an old opportunity.
Ingestion and evaluation share the same quote identity, mode, freshness, and future-timestamp checks.
Old snapshots may be retained for audit, but future-dated or wrong-identity books cannot replace a valid latest snapshot.
The API independently expires per-market health as quote deadlines pass, even when no new ingestion cycle runs.
History intentionally retains expired calculations.

Live results are `quote_supported_estimate`, conditional on balances, venue access, account limits, and complete fills.
Automatic execution, short selling, inverse mappings, multi-outcome portfolios, and transfers are not implemented.

## API

Product routes are read-only under `/api/v1`.
Lists support `limit` and `offset`, with at most 200 rows per page.

| Route | Result |
| --- | --- |
| `/status` | Mode, exchange health, monitored-set limit, and transport |
| `/markets` | Normalized markets, raw metadata, and term hashes |
| `/markets/{market_id}` | One market |
| `/markets/{market_id}/book` | Latest persisted book, potentially stale |
| `/markets/{market_id}/versions/{terms_hash}` | Historical settlement metadata |
| `/snapshots/{snapshot_id}` | Exact historical book |
| `/matches` | Current candidates and reviewed decisions |
| `/opportunities` | Current unexpired opportunities |
| `/opportunities/history` | Historical calculations |
| `/evaluations` | Results including blocked reasons |
| `/stream` | SSE snapshots of opportunities and health |

SSE sends complete snapshots of the first 200 current opportunities, so reconnection receives a fresh view without event replay.
Use paginated REST requests for larger result sets.
FastAPI serves documentation at `/docs` and OpenAPI at `/openapi.json`.
Export the schema for the future TypeScript client with:

```sh
.venv/bin/python -m arbbot.api.export_schema --output docs/openapi.json
```

## Operations and remaining work

`/health/live` checks the process and `/health/ready` checks database access and the initial schema.
Ingestion health is reported separately at `/api/v1/status`.
Each exchange includes `discovery_ok`, `fresh_book_count`, and a `market_health` list containing per-market status, safe error codes, snapshot IDs, quote timestamps, and freshness deadlines.
`book_count` describes usable books at the last ingestion check; `fresh_book_count` is recalculated at request time.
The same health information appears in SSE snapshots.
After deploying this change, older health records without per-market details remain ineligible until the upgraded worker completes its next cycle.
Workers emit JSON logs and the API exposes Prometheus HTTP metrics at `/metrics`.
OpenTelemetry tracing, worker metrics, dashboards, and alerts remain to be integrated.

Audit tables currently grow with ingestion activity.
Establish partitioning, archival, and retention before sustained production ingestion at scale.
Public deployment also requires authentication, authorization, secret management, backups, and recovery validation.
These are extensions to the integrated product architecture rather than separate component products.

## Official exchange references

Adapters were checked against official documentation and small live read-only requests during implementation.

- [Kalshi market discovery](https://docs.kalshi.com/api-reference/market/get-markets)
- [Kalshi order-book format](https://docs.kalshi.com/getting_started/orderbook_responses)
- [Kalshi authenticated order books](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- [Kalshi request signing](https://docs.kalshi.com/getting_started/api_keys)
- [Polymarket market discovery](https://docs.polymarket.com/market-data/discover-markets)
- [Polymarket order books](https://docs.polymarket.com/market-data/prices-order-books)
- [Polymarket fees](https://docs.polymarket.com/trading/fees)

## Structured contract interpretations

Live pair approval additionally requires evidence-backed definitions and review hashes binding those definitions.
See [the contract matching workflow](contract-matching.md) for authoring, comparison fields, configuration, and migration of existing reviews.
Comparisons and evidence are exposed on matches and retained on opportunities.
