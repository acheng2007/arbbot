# Kalshi and Polymarket US workflow

The integrated workflow discovers catalogs, proposes counterpart contracts, monitors complete pairs, calculates reviewed executable estimates, and publishes eligible positive results through FastAPI and SSE to Next.js.
A proposed counterpart is not settlement equivalence.
Missing evidence, access, fees, quotes, or supported settlement outcomes blocks calculation or publication.
The platform does not place orders, connect private trading accounts, hold funds, or transfer money.
Browser OIDC and browser review editing remain deferred.

## Runtime and defaults

Run PostgreSQL and upgrade migrations before starting API or worker processes.
The worker is persistent and independent of API requests and browser sessions.
Discovery, source enrichment, matching, book polling, fee refresh, and evaluation have independent supervised schedules.
Missed work coalesces and quote cycles do not overlap.

```sh
docker compose -p arbbot-local up -d db
export ARBBOT_MODE=live
export ARBBOT_ENABLED_VENUES='["kalshi","polymarket_us"]'
(cd backend && ../.venv/bin/python -m alembic upgrade head)
.venv/bin/python -m arbbot.workers.main
```

Run the API in another terminal with the same backend environment.

```sh
.venv/bin/python -m uvicorn arbbot.api.app:app --host 127.0.0.1 --port 8000
```

Run the browser application against that API.

```sh
cd apps/web
BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Live discovery defaults to broad catalogs and both US venues.
The default monitoring budget is 50 contracts per venue with a five-second polling target, thirty-second quote-age limit, and ten-second cross-venue skew limit.
Slow exchange responses can miss the polling target; age and skew gates still apply.
Catalog page size and traversal are independent of monitoring budgets.
Use `ARBBOT_MONITORING_LIMITS='{"kalshi":25,"polymarket_us":40}'` for separate venue budgets.
`ARBBOT_DISCOVERY_LIMIT` remains the default monitoring-budget fallback and focused-discovery bound for existing configurations.
Watchlists prioritize broad discovery; set `ARBBOT_DISCOVERY_MODE=focused` to make watchlists exclusive.
Persisted scopes prevent resuming incompatible catalog queries.
Supported catalogs, explicit exclusions, continuation progress, source gaps, and per-market quote health are inspectable through the API.

Sizing uses whole contracts, a default $1,000 capital limit, a ten-basis-point slippage reserve, and a $0.01 minimum positive estimate.
US NO exposure shorts the native instrument.
The API keeps native price, short proceeds, gross collateral, net buying power, acquisition cost, fees, and reviewed settlement payouts separate.
Capital reserves gross US short collateral conservatively.
Balances, inventory, full fills, and non-atomic execution remain explicit assumptions.

## Operator review

Use the existing authenticated reviewer APIs or the local operator CLI.
Local records identify the operating-system user; remote records identify the authenticated bearer principal.
Inputs and current revision IDs are described in `docs/execution.schema.json`, `docs/definitions.schema.json`, and OpenAPI.

Capture an applicable official document using a JSON request containing `market_id`, `url`, and `label`.
Only verified official hosts and bounded document formats are accepted.

```sh
.venv/bin/python -m arbbot.reviews.operator capture source capture-request.json
```

Use the returned artifact ID, its content hash, and exact captured quotations in applicability configuration.
Select specifications and amendments explicitly and cite the amendment inventory.
A filename or title resemblance is insufficient applicability evidence.
Import reviewed applicability, then current definition drafts and an equivalence decision covering joint exceptional settlement outcomes.
The installation access profile separately records jurisdiction, explicit products, shorting permission, fee-account class, supporting evidence, and expiry.
Unknown, restricted, expired, or absent access blocks publication.
Public summaries omit supporting evidence and jurisdiction details.

```sh
.venv/bin/python -m arbbot.reviews.operator validate configuration applicability.json
.venv/bin/python -m arbbot.reviews.operator import configuration applicability.json
.venv/bin/python -m arbbot.reviews.operator validate draft definition.json --market-id kalshi:EXAMPLE
.venv/bin/python -m arbbot.reviews.operator import draft definition.json --market-id kalshi:EXAMPLE
.venv/bin/python -m arbbot.reviews.operator validate decision decision.json
.venv/bin/python -m arbbot.reviews.operator import decision decision.json
```

Validation runs repository evidence, expiry, and optimistic-concurrency checks and rolls back its transaction.
Use `validate ... --schema-only` only when structural validation without a database is intended.
Imports commit immutable revisions and current heads; stale expected revisions return conflicts.
Changed document bytes invalidate dependent review generations even when the old bytes later return.
Shared documents invalidate every dependent market.
Transient source failures withdraw estimates; identical-source recovery requires fresh calculation without inventing changed settlement terms.
Original terms and captured bytes remain available for audit.

## Fee policies and publication

Policies refresh outside the pure financial engine and are immutable, versioned calculation inputs.
Kalshi retrieval includes current series policies, complete event override history, and scheduled series/event changes.
The captured general fee formula and rounding documentation must remain available and match the supported implementation.
Unsupported models or missing execution granularity return unavailable fees.
Kalshi's bound is independent of unknown fragmentation within aggregated book levels and includes possible trade and balance rounding at the documented minimum execution increment.
It deliberately makes no assumption that the order's final accumulator is fully rebated.
Non-direct/FCM account charges are currently unavailable because third-party fees cannot be verified from the exchange schedule alone.
They require additional verified policy support before enabling estimates for that account class.

US standard taker estimates use the documented cumulative half-even rounded cap.
The implementation uses the higher supported standard coefficient of 0.10 as a conservative bound across standard and Table Tennis instruments.
Maker rebates, discounts, combos, and unverified account-specific schedules are excluded.
Live fee failures never borrow simulation cost envelopes.
Failures produce explicit unavailable policy revisions, withdraw dependent estimates, and do not stop unrelated refreshes.
Bounded fee cohorts rotate with durable offsets.

Positive preliminary results refetch both legs concurrently and recalculate.
Publication then checks current matching generation, exact current snapshots, market state, per-market health, quote age/skew, approval, access, applicability, and fee versions in one transaction.
An estimate expires at its earliest input deadline.
Invalid inputs withdraw estimates, and recovery calculates new estimates rather than replaying old ones.
Pair publication does not replace unrelated matching generations or evaluations.
Latest evaluation heads avoid scanning the entire audit history on each browser refresh.
Exact opportunity details retain the original calculation and expose eligible/invalidated status plus current quote, approval, configuration, and feed invalidation reasons.
Migration `b023_evaluation_heads` preserves historical payloads, backfills latest heads, and stores signed financial metrics with unscaled PostgreSQL `NUMERIC`.
International venue identities and historical payloads remain readable; they are not an additional US trading route.

## Verification

Run the complete backend suites against SQLite and an isolated PostgreSQL database.
The PostgreSQL test fixture creates and removes its own unique test schemas.

```sh
.venv/bin/python -m pytest backend/tests -q
ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot .venv/bin/python -m pytest backend/tests -q
```

Run the integrated acceptance harness against PostgreSQL.
It upgrades a unique schema, delegates recorded HTTP responses through production adapters, runs the actual persistent worker and FastAPI processes, and connects Next.js to that API.
It preserves its isolated schema, logs, request journal, recording, screenshots, and results for audit and stops only the processes it started.
Stop other ingestion workers using the same PostgreSQL database before running the harness, or supply a separate database URL.
The worker lease is shared across schemas in a database.
Failed runs retain public API and persisted-input diagnostics in `diagnostics.json`, with schema and service ports in `runtime.json`.

```sh
.venv/bin/python backend/scripts/run_acceptance.py --output /tmp/arbbot-acceptance
```

The four independent synthetic scenarios cover profitable, unprofitable, blocked, and invalid results.
Synthetic contracts explicitly declare their complete settlement facts and shared cancellation condition.
Authentic exchange recordings remain unchanged and unapproved alongside them.
Replay has no network fallback, rejects non-GET requests and private exchange credentials, and labels market, quote, comparison, and opportunity provenance.
The browser banner identifies the running recorded backend; synthetic profits cannot appear as live exchange evidence.
Acceptance covers more than 200 counterparts, catalog-wide filtering, exact details, pair rotation, SSE, publication-time price movement, source/review/access/fee withdrawal, expiry, restart, outage, recovery, and desktop/mobile layouts.
`--no-browser` is a diagnostic subset and does not replace full acceptance.

Run ordinary frontend fixture coverage separately from the connected acceptance harness.

```sh
cd apps/web
npm run test
npm run typecheck
npm run lint
npm run generate:api:check
npm run build -- --webpack
npm run test:e2e
```

Use `.venv/bin/python backend/scripts/smoke_us.py` for opt-in live, public, read-only catalog/book checks and matching evidence.
Live contract counts, prices, and depth vary and are not fixed acceptance assertions.
A positive live opportunity is not required.
Real installation access and real equivalence decisions are never synthesized to make tests pass.
