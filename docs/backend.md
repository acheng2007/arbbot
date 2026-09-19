# Backend behavior and operations

## Ingestion

The worker discovers a bounded set of markets, retrieves full REST order-book snapshots, persists normalized results, discovers candidates, evaluates verified pairs, and publishes a coherent opportunity view.
Exchange requests use bounded concurrency, pacing, timeouts, and retries for transport errors, rate limits, and selected server failures.
Every cycle reads complete snapshots, so recovery does not depend on replaying deltas.
Exchange WebSocket ingestion and sequence reconciliation are not implemented yet.

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
Omit the review file to ingest markets and discover unverified candidates without producing live opportunities.
Use a separate database for production and simulation even though queries isolate modes.

The Kalshi adapter supports optional RSA signing through `ARBBOT_KALSHI_KEY_ID` and `ARBBOT_KALSHI_PRIVATE_KEY_PATH`.
Keys stay in local files and are never returned through the API.
Kalshi's public tutorial and authenticated endpoint reference differ on authentication requirements; configure a key if public reads are rejected.
Authentication failures appear in exchange health rather than triggering a simulation fallback.

For live containers, use a local Compose override setting both API and worker to live mode, pass worker configuration explicitly, and mount credentials and review files read-only.
Do not put secrets in images or source control.
No adapter places orders or accesses account balances.

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
Partial exchange failures suppress affected opportunities until a complete healthy cycle succeeds.
The API separately filters expired opportunities and requires healthy worker heartbeats.
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
