# Implementation roadmap

Remaining work is split into [modular contributor issues](contributing/README.md), with a [GitHub master tracker](https://github.com/acheng2007/arbbot/issues/41).
The issue index retains published dependencies and file boundaries; GitHub issue/PR status has not been rechecked for this documentation update.

This checklist tracks one integrated product, organized by workstream.
Checked items are implemented and locally validated; unchecked items remain work to do.
A narrow implementation is marked complete only at its stated scope.
Status was reconciled against the repository and local checks on October 11, 2026.
Items labeled **local, uncommitted** exist in the working tree and pass the current automated suite, but are not a committed or live-validated release.
See the [integrated status handoff](contributing/project-status-handoff.md) for validation limits and the [historical handoffs](contributing/history/README.md) for prior delivery evidence.

## Active direction: US-accessible market comparison

The October 1 direction supersedes the Opinion/Limitless four-venue expansion plan.
Compare all discovered supported contracts across eligible US trading venues, find equivalent outcomes, and calculate price differences after fees and available depth.
Venue count is evidence-driven, with no fixed four-venue requirement.
See [the US venue expansion plan](us-venue-expansion.md) for sequencing, eligibility gates, and the first implementation milestone.
Opinion and Limitless are excluded from this milestone.
The existing Polymarket adapter is International and must not be treated as Polymarket US or as an eligible US execution route.
Local enabled-venue filtering and a distinct Polymarket US discovery adapter exist.
Account/product eligibility filtering remains unfinished; enabled venues do not establish trading eligibility.

## Exchange integrations

- [x] Kalshi and Polymarket International REST market and order-book adapters.
- [x] Explicit market watchlists, bounded discovery, pacing, retries, and concurrent book reads.
- [x] Source metadata preservation and explicit simulation mode.
- [x] Initial recorded corpus of nine real contracts with capture timestamps, URLs, and labels.
- [x] Targeted discovery of supported same-event candidates across CPI and Fed rate-hike families.
- [x] Kalshi series metadata and linked contract/source enrichment.
- [ ] A reviewed, supported live cross-exchange pair.
- [x] Polymarket International market-specific fee normalization and provider with recorded policy evidence; not yet consumed by evaluation.
- [ ] Complete tested Kalshi and Polymarket US fee providers, metadata refresh, and automatic evaluation integration; a Kalshi provider exists locally but is unfinished.
- [x] Polymarket International WebSocket books, reconnects, disconnected-feed invalidation, periodic snapshots, and worker lifecycle integration.
- [ ] Kalshi and eligible US venue streaming plus immediate event publication/revalidation.
- [x] Negative-risk assessment with recorded evidence and regression tests; continued exclusion is the decision, not implementation of support.
- [x] Initial Polymarket US catalog/book/fee/restriction recordings and rule-backed World Series overlap candidate with Kalshi (**local, uncommitted**).
- [x] Separate Polymarket US discovery/book adapter with invalid-book rejection and explicit evaluation blocking (**local, uncommitted**).
- [ ] Complete the Polymarket US capability assessment with rulebook/clarification evidence, fee semantics, eligibility inputs, and fresh integrated validation.
- [ ] Assess Crypto.com Predictions/CDNA and ForecastEx/CME independently before implementing additional adapters.
- [x] Remove the uncommitted Opinion and Limitless expansion and defer both venues outside the US milestone.
- [x] Stable venue registration, configured adapter construction, venue metadata API, and enabled-venue catalog filtering (**local, uncommitted**).
- [ ] Complete capability/eligibility-aware multi-venue ingestion, matching, evaluation, and API contracts, preserving historical International identities and reviews.

## Backend matching

- [x] Structured contract definitions and quotation validation.
- [x] Shared-event candidate retrieval with title-similarity fallback.
- [x] Field-level settlement comparisons, unknowns, and conflicts.
- [x] Human approval bound to source terms and definition hashes.
- [x] Narrow deterministic CPI drafts and extraction inspection endpoint.
- [x] Initial real-contract replay, labeled coverage report, and near-match rejection tests.
- [x] Recorded Kalshi primary-rule grammar for threshold and reporting-period drafts.
- [x] Broader labeled corpus with supported same-event candidate pairs and material settlement negatives.
- [x] Version 2 canonical measurement fields for seasonal adjustment, rounding, revision selection, and observation boundaries, with legacy approval invalidation.
- [x] Narrow deterministic Fed rate-hike drafts; unresolved wording differences remain candidates/conflicts.
- [x] Rule-backed World Series event identities and team/year negatives (**local, uncommitted**); incomplete settlement evidence prevents approval.
- [ ] Expand extraction across supported real contract wording.
- [ ] Evaluate structured LLM extraction for cases deterministic parsers cannot handle.

## Backend arbitrage

- [x] Complementary YES/NO strategies with depth-based whole-contract sizing.
- [x] Reviewed fee and conversion bounds, slippage reserve, and capital limits.
- [x] Minimum payout across supplied settlement scenarios.
- [x] Quote freshness, identity, timing, and review validity checks.
- [ ] Consume evidence-backed venue fee quotes during depth-dependent sizing, including rounding, unknown/stale policies, and supported slippage assumptions.
- [x] Explicit YES/NO payouts, source-backed cancellation/fallback/ambiguous-resolution inventories, and scenario mapping/completeness validation.
- [ ] Validate semantic completeness and reachable joint exceptional outcomes against supported real US pairs; declared-inventory coverage does not prove all outcomes are modeled.
- [ ] Immediate opportunity rechecks with live books.
- [ ] Evidence-backed account/product eligibility gates for actionable US estimates, with unknown access blocking publication.
- [ ] Venue access, balance, and inventory validation if execution is later authorized.

## Backend API and storage

- [x] PostgreSQL models, migrations, source versions, snapshots, and evaluation history.
- [x] Immutable settlement source artifacts with explicit retrieval failures, bounded documents, and audit history.
- [x] Read-only market, matching, extraction, opportunity, health, and audit APIs.
- [x] Pagination, SSE updates, and published OpenAPI schemas.
- [x] Per-market feed health and suppression of affected opportunities.
- [x] Persistent editable draft and review records replacing the file-only workflow by default.
- [x] Authentication and authorization for mutations.
- [x] Review APIs with concurrent-edit protection and audit history.
- [x] Search and filtering suitable for the dashboard.
- [x] Database approval consumption and publication/read-time rechecks of exact review revisions, evidence, and expiry.

## Frontend

- [x] Next.js application and generated TypeScript API client.
- [x] Market browser with source rules and ingestion status.
- [x] Side-by-side contract comparison and evidence inspection.
- [ ] Review queue, draft editing, approval, and rejection.
- [x] Read-only opportunity dashboard/details with depth, reviewed costs, payoff scenarios, freshness, and opportunity SSE.
- [ ] Integrate automatic fees, US eligibility, and immediate quote-recheck results into actionable presentation.
- [x] Accessible loading, empty, error/retry, stale, and stream reconnect states for existing read-only screens, with prior browser validation.
- [x] Vitest and Playwright coverage for existing read-only screens, including prior visual review.
- [x] Venue API-driven selection/panels and distinct Polymarket US labeling (**local, uncommitted**).
- [ ] Complete all-counterpart pagination and independent venue-pair presentation; remove the first-200-match and one-pair-per-market limits.
- [ ] Connect catalog-wide search/status controls to existing backend filters instead of filtering only the loaded page.
- [ ] Complete responsive multi-venue comparison and opportunity flows with explicit access, provenance, and venue-specific costs.

## Infrastructure and QA

- [x] Docker Compose services and pinned backend dependencies.
- [x] Backend unit and integration tests on SQLite and PostgreSQL.
- [x] Local Docker smoke workflow for worker, API, PostgreSQL, audit records, and SSE.
- [x] GitHub Actions workflow definition for tests, lint, migrations, corpus, and schema drift.
- [x] Historical successful hosted backend CI evidence recorded in `docs/ci.md` and fixture-backed frontend CI evidence in the frontend handoff history.
- [x] Frontend CI definition for generated contracts, lint, types, unit tests, build, and desktop/mobile fixture browser tests.
- [ ] Hosted checks for the finished US milestone; older successful runs do not validate the current uncommitted tree.
- [x] Structured worker logging and API Prometheus metrics.
- [x] Fixture-backed desktop/mobile browser workflow and historical real live-price smoke checks.
- [ ] Seeded PostgreSQL browser workflow from authenticated draft/review actions through worker evaluation, publication, invalidation, and recovery.
- [ ] Production deployment, secrets management, backup and recovery validation.
- [x] Opt-in OpenTelemetry/OTLP tracing across ingestion, matching, evaluation, publication, and API requests, with trace-correlated logs.
- [ ] Worker health metrics, dashboards, alerts, and real staging collector verification.
- [ ] Seven-day forward paper study with fixed budgets, quote rechecks, rejected candidates, coverage, and opportunity lifetimes.

## Implementation order

1. Finish the existing Kalshi/Polymarket US discovery milestone: restore Docker, validate worker/API/PostgreSQL and desktop/mobile quotes, review recorded evidence, document capability/access blockers, and commit the focused implementation.
2. Establish complete source-backed settlement definitions and reachable exceptional outcomes for a supported US pair, and implement account/product eligibility gates.
3. Complete Kalshi/Polymarket US fee providers and automatic sizing integration, alongside authenticated browser draft editing, approval/rejection/revocation, and conflict handling.
4. Add immediate quote rechecks and a seeded PostgreSQL browser review-to-estimate workflow, including suppression after changed terms, stale books, unknown access, or unavailable fees.
5. Complete counterpart pagination and catalog-wide frontend filters, then assess additional US venues and categories with coverage reports and category-specific settlement evidence.
6. Run the seven-day forward paper study, then complete eligible venue streaming, operational monitoring, staging identity/secrets/collector validation, and backup/recovery rehearsal.

Acceptance requires a reproducible and correctly gated workflow, not a positive opportunity.
If the recorded candidate has incompatible settlement terms, retain the conflict and assess another supported pair.

No phase authorizes automatic trading, custody, or transfers.
Two-leg comparison remains the initial strategy boundary.

## Current validation and next task

The integrated baseline includes live-price ingestion, source enrichment, version 2 definitions, persistent reviews, authenticated review APIs, read-only opportunity screens, stream infrastructure, and tracing.
The current uncommitted US work adds discovery, a venue registry/API, candidate extraction, and venue-aware browser panels; these are not a completed US evaluation release.
Browser review editing, account/product eligibility, automatic fee integration, and all-counterpart pagination remain unfinished.
Existing Polymarket International fixtures remain useful for historical regression tests but do not establish US trading eligibility.
The abandoned expansion was uncommitted and was removed without changing the database or existing historical reviews.

October 11 local validation passed 430 SQLite backend tests, 56 frontend tests, frontend types/lint/generated-client drift, and backend lint/format.
Docker is unavailable, so fresh PostgreSQL, migration, live API, production build, and browser validation have not been performed for the current US tree.
Historical PostgreSQL, browser, and hosted CI results remain evidence for their recorded scopes and commits only.

Next action: restore Docker and finish integrated validation of the existing Kalshi/Polymarket US discovery work before enabling evaluation or adding another venue.
See the [US expansion handoff](contributing/us-expansion-handoff.md) for the focused acceptance criteria.
