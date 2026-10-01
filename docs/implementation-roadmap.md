# Implementation roadmap

Remaining work is split into [modular contributor issues](contributing/README.md), with a [GitHub master tracker](https://github.com/acheng2007/arbbot/issues/41).
Each issue specifies one PR, file ownership, dependencies, acceptance criteria and validation.

This checklist tracks one integrated product, organized by workstream.
Checked items are implemented and locally validated; unchecked items remain work to do.
A narrow implementation is marked complete only at its stated scope.

## Active direction: US-accessible market comparison

The October 1 direction supersedes the Opinion/Limitless four-venue expansion plan.
Compare all discovered supported contracts across eligible US trading venues, find equivalent outcomes, and calculate price differences after fees and available depth.
Venue count is evidence-driven, with no fixed four-venue requirement.
See [the US venue expansion plan](us-venue-expansion.md) for sequencing, eligibility gates, and the first implementation milestone.
Opinion and Limitless are excluded from this milestone.
The existing Polymarket adapter is International and must not be treated as Polymarket US or as an eligible US execution route.
US eligibility filtering is planned work, not a capability of the restored demo.

## Exchange integrations

- [x] Kalshi and Polymarket International REST market and order-book adapters.
- [x] Explicit market watchlists, bounded discovery, pacing, retries, and concurrent book reads.
- [x] Source metadata preservation and explicit simulation mode.
- [x] Initial recorded corpus of nine real contracts with capture timestamps, URLs, and labels.
- [x] Targeted discovery of supported same-event candidates across CPI and Fed rate-hike families.
- [x] Kalshi series metadata and linked contract/source enrichment.
- [ ] A reviewed, supported live cross-exchange pair.
- [ ] Market-specific fee retrieval and normalization.
- [ ] Exchange WebSocket books, reconnects, and reconciliation.
- [ ] Assess negative-risk contract support separately before admitting those markets.
- [ ] Prioritize US-accessible venues for the discovery product: evaluate Polymarket US, Crypto.com Predictions, and ForecastEx/CME through documented market-data APIs before adding new adapters.
- [x] Remove the uncommitted Opinion and Limitless expansion and defer both venues outside the US milestone.
- [ ] Generalize the backend from its current Kalshi/Polymarket assumptions to an extensible venue registry, multi-venue matching, ingestion, evaluation, storage, and API contracts. This may require substantial backend rewrites rather than only adding two adapters.

## Backend matching

- [x] Structured contract definitions and quotation validation.
- [x] Shared-event candidate retrieval with title-similarity fallback.
- [x] Field-level settlement comparisons, unknowns, and conflicts.
- [x] Human approval bound to source terms and definition hashes.
- [x] Narrow deterministic CPI drafts and extraction inspection endpoint.
- [x] Initial real-contract replay, labeled coverage report, and near-match rejection tests.
- [x] Recorded Kalshi primary-rule grammar for threshold and reporting-period drafts.
- [x] Broader labeled corpus with supported same-event candidate pairs and material settlement negatives.
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
- [x] Persistent editable draft and review records replacing the file-only workflow by default.
- [x] Authentication and authorization for mutations.
- [x] Review APIs with concurrent-edit protection and audit history.
- [x] Search and filtering suitable for the dashboard.

## Frontend

- [x] Next.js application and generated TypeScript API client.
- [x] Market browser with source rules and ingestion status.
- [x] Side-by-side contract comparison and evidence inspection.
- [ ] Review queue, draft editing, approval, and rejection.
- [ ] Opportunity dashboard with depth, costs, payoff scenarios, and freshness.
- [ ] Accessible loading, empty, error, stale, and reconnect states.
- [x] Vitest and Playwright coverage for existing read-only screens, including prior visual review.
- [ ] Review and potentially rewrite frontend market, comparison, and opportunity flows so they support any number of venues with explicit two-leg comparisons, venue-specific status and costs, and clear provenance. Avoid hard-coded two-platform presentation.

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

1. Assess Polymarket US, Crypto.com Predictions/CDNA, and ForecastEx/CME access, source evidence, books, fees, restrictions, and actual overlap with Kalshi.
2. Implement US eligibility and an extensible venue registry, preserving historical International IDs and review hashes.
3. Integrate Polymarket US first, then Crypto.com, then ForecastEx and CME separately through validated broker access; revise the order if evidence or access blocks a candidate.
4. Expand catalog discovery beyond CPI/Fed, with explicit supported categories and coverage reports; add settlement parsers and review evidence before enabling evaluation for each category.
5. Complete paginated event comparison, authenticated review editing, fees, exceptional-settlement validation, and live quote rechecks.
6. Run a seven-day forward paper study, then finish streaming, operational monitoring, staging, and recovery validation.

No phase authorizes automatic trading, custody, or transfers.
Two-leg comparison remains the initial strategy boundary.

## Current validation and next task

The restored baseline includes the live-price demo, source enrichment, persistent reviews, authenticated review APIs, and existing read-only frontend screens.
Browser review editing, generalized venue selection, and all-counterpart pagination remain unfinished.
Existing Polymarket International fixtures remain useful for historical regression tests but do not establish US trading eligibility.
The abandoned expansion was uncommitted and was removed without changing the database or existing historical reviews.

Next action: capture a reproducible Polymarket US capability assessment and immutable public market, rule, book, and fee evidence, including eligibility restrictions and measured overlap with Kalshi.
Document unsupported contracts and missing overlap rather than assuming catalog coverage or executable returns.
See [the US expansion handoff](contributing/us-expansion-handoff.md) for the rollback and validation record.
