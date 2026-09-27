# Backend production handoff

The active goal is to complete the backend end to end for production, testing when necessary.
The goal remains incomplete.

## Active implementation: September 27, 2026

Work now continues in `/Users/adam/Project/arbbot` on `backend/completion`, based on the running `demo/live-prices` workstream.
Integrated current `origin/main` (`aacc456`) with the demo's Polymarket stream and paired-price frontend.
Resolved the stream package description and retained both WebSocket and authentication/tracing dependencies.
Regenerated the frontend API client from the combined schema.
The combined tree passes 300 SQLite backend tests, Ruff lint/format, and frontend typechecking.
The live API reproduction returned an empty matches array; the worker only samples 20 independent markets per venue.
The existing source-enrichment branch uses a different storage contract and cannot be merged unchanged.

Adapted source enrichment to the landed immutable repository, retaining recorded venue metadata and the original source migration.
Live ingestion now captures source evidence, semantic source changes invalidate definitions, and incomplete sources block settlement compatibility without hiding known event identities.
Added mode-isolated, paginated source metadata and attachment-download APIs and regenerated the client.
Validation: 319 tests pass on both SQLite and PostgreSQL (isolated schemas on port 55433); Ruff and frontend typechecking pass.
Added independently scheduled event-family discovery and enrichment with durable mode-isolated reports at `/api/v1/discovery`.
Watchlists retain precedence; bounded scans report excluded instruments, unrelated categories, missing sources and coverage limits.
Stalled catalog refreshes do not block quotes, and failed refreshes cannot extend catalog expiration.
The additive catalog migration and discovery checks bring the suite to 329 tests, passing on both SQLite and PostgreSQL; all 55 frontend tests pass after updating the generated-client expectation for the already-landed search parameters.
The local Docker stack rebuilt and migrated successfully on September 25.
Live inspection verified source download metadata and catalog reports and caught incidental CPI citations in grocery-price descriptions; the relevance filter now requires a matching headline.
The final filter change is covered by the targeted regression and deployed in the local worker.
The current CPI scan selects 20 Kalshi markets and no supported Polymarket counterparts; most Polymarket candidates are excluded as unsupported negative-risk instruments.

Implemented durable definition drafts and review revisions (#16), preserving immutable evidence snapshots, actor identity, exact hashes and predecessor chains.
Compare-and-swap writes and parent-row locks prevent concurrent edits from silently overwriting decisions.
Changed drafts, market terms, sources, source failures and expiry invalidate eligibility without erasing audit history.
The additive migration preserves existing markets, source artifacts and discovery reports on upgrade and downgrade.
Validation: 340 backend tests pass on SQLite; the 11 review storage tests also pass on PostgreSQL using isolated schemas, including the strengthened migration preservation check.
Ruff passes.
The new review storage has not been deployed to the local running stack or connected to HTTP mutations and worker approval consumption.
See `docs/review-storage.md` for behavior and limits.

Added explicit YES/NO payouts for each venue to settlement scenarios.
Live matching, durable approval writes and reads, and evaluation reject legacy implicit NO payouts; non-complementary payouts and variable refunds remain unsupported.
The evaluator uses explicit payouts and tests divergent settlement where both purchased legs lose.
The integrated worker/database/API regression proves implicit reviews suppress opportunities and explicit reviews restore eligibility.
Regenerated OpenAPI, review JSON Schema and the TypeScript client.
Validation: 352 backend tests pass on SQLite; all 35 targeted settlement, review storage and contract integration tests pass on PostgreSQL using isolated schemas.
Frontend typechecking and Ruff pass.
See `docs/settlement-validation.md`; scenario completeness is not yet proved by these arithmetic checks.

Added source-backed cancellation, fallback and ambiguous-resolution inventories to canonical definitions, with fixed payouts per named condition.
Live gates require each policy to be modeled or explicitly not applicable and map every declared condition to payout-consistent named scenarios.
Missing/unknown inventories, missing conditions, duplicate mappings and mismatched scenario payouts keep pairs unverified.
Policy evidence is checked against market rules and included in definition hashes, invalidating legacy approvals until reviewed again.
The integrated worker/API test suppresses opportunities when condition coverage is removed.
Validation: 360 SQLite tests pass; all 43 targeted PostgreSQL settlement, contract integration and review repository tests pass, including the final API coverage-removal regression.
Frontend typechecking, Ruff and whitespace checks pass.
This establishes coverage of the declared inventory, not completeness of semantic interpretation or every reachable cross-venue combination.

Implemented authenticated draft and review HTTP routes (#18): current revisions, paginated history, draft writes, approval, rejection and revocation.
The server derives audit identity from verified tokens; viewer/reviewer roles and mutation origins are enforced.
Conflicting edits and stale terms return 409; missing mode-isolated inputs return 404; invalid evidence returns 422 without partial writes.
Extended the TypeScript schema generator for POST request bodies, 201 responses and distinct FastAPI input/output models; existing dashboard reads remain restricted to GET operations.
Validation: 372 SQLite backend tests, 12 review API PostgreSQL tests in isolated schemas, 56 frontend tests, frontend typechecking and Ruff pass.
The pending public Kalshi catalog lookup completed successfully, but no supported positive counterpart was recorded or reviewed.
The real-pair corpus and joint exception interactions remain unfinished and are not implied complete by the API tests.
See `docs/review-api.md` for endpoint contracts and operational limits.

Connected database drafts and approval revisions to live worker matching and evaluation (#19).
Database mode is the default and does not fall back to review files; legacy development requires `ARBBOT_REVIEW_SOURCE=files` on API and worker.
Publication rechecks exact approval revision and eligibility under parent-market locks, and public opportunity reads recheck eligibility in a consistent snapshot before pagination.
Public matches also downgrade stale approvals before status filtering and pagination using bounded keyset batches.
Reapproval requires recalculation; historical results retain the original `review_revision_id`.
Validation: the full 380-test SQLite suite passed before the final rejection parameter case; all nine final worker-review cases pass on SQLite, and all 23 final worker-review/catalog tests pass on PostgreSQL.
The earlier combined PostgreSQL review-provider/storage/API run passed all 30 tests.
Ruff, generated-client drift checking and frontend typechecking pass.
Rebuilt local API and worker with the additive review migration; health returns 200 in live mode, protected drafts return 401 without credentials, and the worker ingests 20 Kalshi books without errors.
No supported paired market or live approval exists, so the local opportunities API correctly returns an empty list.

Recorded eight unchanged supported contracts across Fed rate hikes, recession and Treasury yields, with source URLs, timestamps, payload digests and separate source-reading labels (#6).
The corpus contains a supported same-event rate-hike candidate and hard negatives for terminal year, recession trigger/source, measurement, observation window and strict/inclusive thresholds.
Labels are not human settlement approvals; every recorded pair has material settlement differences.
Added conservative partial Fed rate-hike extraction and a second default discovery family, retaining all instrument eligibility restrictions.
Allowed the exact Federal Reserve source host declared by the Kalshi series.
Validation: 389 backend tests pass, including 29 focused corpus/extraction/discovery checks; the final source-host addition passes the existing source-enrichment tests.
Rebuilt local API and worker; live discovery selects 19 Kalshi and one Polymarket contract.
The local matches API now returns `kalshi:KXFEDHIKE-2-26DEC31` / `polymarket:4620900` with `same_event=true`, `status=candidate` and settlement `conflict`.
Kalshi runs through December 31 while Polymarket ends at the December FOMC decision; no approval or opportunity was fabricated.
See `docs/corpus-cross-exchange.md` for captured rule differences and remaining evidence gaps.

Implemented the market-specific Polymarket fee provider (#13), using observed `feesEnabled` and `feeSchedule` inputs with the currently documented exponent-one price curve.
Unknown, contradictory or stale metadata cannot become implicit zero fees; explicit disabled schedules and taker-only maker fees retain provenance and zero-fee reasons.
Quotes bind market/mode/native pUSD unit and round upward per supplied fill at five decimal places, without assuming rebate credits.
Added two unchanged public fee records and pinned payload digests, plus synthetic boundary, malformed and fee-free cases.
Validation: all 52 focused fee policy and shared fee-contract tests pass; Ruff and whitespace checks pass.
This provider is not yet consumed by the engine, and supplied fills do not prove actual execution fragmentation.
See `docs/polymarket-fees.md`.
Current official Kalshi documentation additionally describes six-decimal trade-fee rounding, balance precision of 0.0001 for direct members versus 0.01 for other members, and per-order rounding accumulators with capped rebates.
The official OpenAPI schema documents event overrides and scheduled series/event fee changes; do not substitute the older PDF's simple cent rounding for the current mechanics.

Next action: implement the Kalshi fee provider (#12) with observed series/event overrides and current rounding mechanics, then connect both providers to metadata refresh and depth-dependent evaluation (#14).
Live settlement approval remains blocked on source completeness and joint exception validation (#10).
Fees, stream lifecycle/revalidation, observability, deployment and recovery remain active scope.
Do not infer live equivalence from titles or create human approvals automatically.
No change to main, remote publication, trading or custody is included.

## Historical integration of foundations

The user explicitly authorized reviewing and merging passing PRs #44 and #46 through #51.
PRs #44 (canonical definitions) and #47 (catalog filtering) landed externally in main at `f91a639a809db8c6562b1793028aa693d7e97f3f`.
This integration adds #46 (fee contracts), #48 (authentication), #49 (stream contracts), #50 (tracing), and #51 (hosted CI evidence).
PR #45 is excluded because main already contains a separate source-storage implementation at `c07ebb6`, migration `d0cc5e73c848`.
Use the landed source interfaces.

Workspace: `/private/tmp/arbbot-backend-integration`, initially detached from main for the authorized merge sequence.
All new local merge commits use the configured user's author and committer identity, verified after each commit.
The current commit is prepared for a normal fast-forward push to main; do not force-push over concurrent changes.
No orders, custody, fund transfers, or private account access are authorized.

## Review and validation

Every merged feature head passed hosted backend checks before publication:
- Fees: `52cdafb34bb207509a46b6533bffc1f79dc27c07`, run 35679642080.
- Authentication: `ce0d0fa613ab9851ecb0680c417be3a40f926cb2`, run 35679646371.
- Streams: `20b3421ddfceda98a2d3bced55a6da3eeedc463a`, run 35679650092.
- Tracing: `4055684c15be26fc8522e234ac9da939a5decf53`, run 35679653623.
- CI documentation: `2ceacedc5ea759d84b572b61f0f2411ac829f5be`, run 35679660358.

Hosted checks include SQLite, PostgreSQL, migrations, recorded corpus output, and generated-schema drift.
The combined local tree passes all 284 SQLite tests, Ruff lint/format, and OpenAPI comparison.
Authentication/tracing merge conflicts were resolved by retaining both configurations, dependencies, API state and cleanup.
A regression proves tracing shutdown flushes its pending request even if authenticator cleanup raises.
The API returns the expected unauthenticated response with trace correlation when tracing is enabled.

Previous review reproduced and fixed two stream rollback cases, a slow-stream JWKS lock hang, and the import-time timestamp race in quote tests.
JWKS fetching now has a five-second total network deadline, closes timed-out responses, releases concurrent callers, and recovers after the retry cooldown.
No financial or eligibility assertions were weakened.
Docker Desktop is manually paused; do not claim a fresh combined local PostgreSQL run.
The earlier disposable `arbbot-foundation-tests` container may still exist because cleanup was interrupted and Docker is paused.

The earlier integration handoff is superseded by the active implementation and next action above.

## Remaining production scope

Source enrichment is underway on remote branch `data/3-4-source-enrichment`; inspect its latest state and ownership before overlapping.
Real overlapping-event discovery, labeled supported pairs, expanded extraction, exceptional settlements, venue fee policies and engine/slippage integration remain.
Live venue streams, worker lifecycle integration, opportunity revalidation, health metrics/dashboards/alerts, staging deployment and recovery rehearsal remain.
The negative-risk assessment is completed in main and continues to exclude unsupported instruments.
Render and Auth0 were recommended; provider configuration, real identity and collector behavior, deployment and restoration are not verified.
Preserve the original worktree's user changes, including untracked `.specstory/`.
