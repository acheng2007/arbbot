# Implementation roadmap

Remaining work is split into [modular contributor issues](contributing/README.md), with a [GitHub master tracker](https://github.com/acheng2007/arbbot/issues/41).
Each issue specifies one PR, file ownership, dependencies, acceptance criteria and validation.

This checklist tracks one integrated product, organized by workstream.
Checked items are implemented and locally validated; unchecked items remain work to do.
A narrow implementation is marked complete only at its stated scope.

## Exchange integrations

- [x] Kalshi and Polymarket REST market and order-book adapters.
- [x] Explicit market watchlists, bounded discovery, pacing, retries, and concurrent book reads.
- [x] Source metadata preservation and explicit simulation mode.
- [x] Initial recorded corpus of nine real contracts with capture timestamps, URLs, and labels.
- [ ] Targeted discovery of overlapping supported event families.
- [ ] Kalshi series metadata and linked contract/source enrichment.
- [ ] A reviewed, supported live cross-exchange pair.
- [ ] Market-specific fee retrieval and normalization.
- [ ] Exchange WebSocket books, reconnects, and reconciliation.
- [ ] Assess negative-risk contract support separately before admitting those markets.

## Backend matching

- [x] Structured contract definitions and quotation validation.
- [x] Shared-event candidate retrieval with title-similarity fallback.
- [x] Field-level settlement comparisons, unknowns, and conflicts.
- [x] Human approval bound to source terms and definition hashes.
- [x] Narrow deterministic CPI drafts and extraction inspection endpoint.
- [x] Initial real-contract replay, labeled coverage report, and near-match rejection tests.
- [x] Recorded Kalshi primary-rule grammar for threshold and reporting-period drafts.
- [ ] Broader labeled corpus with supported positive cross-exchange pairs.
- [ ] Canonical measurement details for seasonal adjustment, rounding, and publication versions.
- [ ] Expand extraction across supported real contract wording.
- [ ] Evaluate structured LLM extraction for cases deterministic parsers cannot handle.

## Backend arbitrage

- [x] Complementary YES/NO strategies with depth-based whole-contract sizing.
- [x] Reviewed fee and conversion bounds, slippage reserve, and capital limits.
- [x] Minimum payout across supplied settlement scenarios.
- [x] Quote freshness, identity, timing, and review validity checks.
- [ ] Automated exchange-specific fee calculations.
- [ ] Stronger exceptional-settlement modeling and review completeness checks.
- [ ] Immediate opportunity rechecks with live books.
- [ ] Venue access, balance, and inventory validation if execution is later authorized.

## Backend API and storage

- [x] PostgreSQL models, migrations, source versions, snapshots, and evaluation history.
- [x] Immutable settlement source artifacts with explicit retrieval failures, bounded documents, and audit history.
- [x] Read-only market, matching, extraction, opportunity, health, and audit APIs.
- [x] Pagination, SSE updates, and published OpenAPI schemas.
- [x] Per-market feed health and suppression of affected opportunities.
- [ ] Persistent editable draft and review records replacing the file-only workflow.
- [ ] Authentication and authorization for mutations.
- [ ] Review APIs with concurrent-edit protection and audit history.
- [ ] Search and filtering suitable for the dashboard.

## Frontend

- [ ] Next.js application and generated TypeScript API client.
- [ ] Market browser with source rules and ingestion status.
- [ ] Side-by-side contract comparison and evidence inspection.
- [ ] Review queue, draft editing, approval, and rejection.
- [ ] Opportunity dashboard with depth, costs, payoff scenarios, and freshness.
- [ ] Accessible loading, empty, error, stale, and reconnect states.
- [ ] Vitest and Playwright coverage, including visual review.

## Infrastructure and QA

- [x] Docker Compose services and pinned backend dependencies.
- [x] Backend unit and integration tests on SQLite and PostgreSQL.
- [x] Local Docker smoke workflow for worker, API, PostgreSQL, audit records, and SSE.
- [x] GitHub Actions workflow definition for tests, lint, migrations, corpus, and schema drift.
- [ ] First successful hosted CI run for the new workflow.
- [x] Structured worker logging and API Prometheus metrics.
- [ ] Full browser end-to-end workflow.
- [ ] Production deployment, secrets management, backup and recovery validation.
- [ ] Worker metrics, tracing, dashboards, and alerts.

## Implementation order

1. Data foundation: initial real-contract fixtures and CI definition are complete; next enrich source metadata and discover genuinely overlapping supported contracts.
2. Review workflow: implement persistent reviews and authenticated APIs alongside frontend market and comparison screens.
3. Opportunity workflow: automate costs, strengthen scenario validation, and build the opportunity dashboard.
4. Live reliability: implement WebSockets, recovery, freshness UX, and monitoring.
5. Production readiness: validate the full browser workflow, deployment, and operational controls.

Frontend read-only screens can proceed alongside data foundation work using existing APIs.
Approval UI depends on authenticated review APIs.
No phase authorizes automatic trading, custody, or transfers.

## Current validation and next task

The initial corpus contains two Kalshi CPI markets and seven Polymarket markets covering annual/monthly CPI, core CPI, foreign inflation, PCE, and Treasury yields.
Six Polymarket fixtures are negative-risk contracts excluded by current adapters.
The original parser extracted zero of 63 labeled fields.
The updated parser extracts 14 correct fields with no incorrect fields in this small sample.
This is a coverage baseline, not proof of general extraction accuracy or an actionable arbitrage pair.

Settlement source artifacts are now persisted with immutable content, explicit retrieval failures, and audit history, but nothing fetches evidence into that store yet.
The next backend task is source and series enrichment plus targeted discovery of supported overlapping contracts.
Kalshi market-level rules in the sample do not independently establish jurisdiction or the source publisher.
Those fields must remain unknown until the relevant source evidence is ingested.
See [recorded contract validation](recorded-contracts.md) for commands and limitations.
