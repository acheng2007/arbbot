# Contributor issue index

The [GitHub master tracker](https://github.com/acheng2007/arbbot/issues/41) is the entry point for claiming work.
Each implementation issue is scoped to one PR; the tracker itself is not a single implementation task.
GitHub is authoritative for current status and assignees.
This index records dependency and file boundaries at publication time.

## Current priorities: October 11, 2026

The [implementation roadmap](../implementation-roadmap.md) is the reconciled product checklist.
The [integrated status handoff](project-status-handoff.md) records the current branch, checks, blockers, and single next action.
Issue numbers below identify the published work breakdown; implemented scope is not a claim that an entire issue is closed or that a remote PR has merged.
Remote issue/PR states were not refreshed during this documentation reconciliation.

The current baseline already includes source storage/enrichment, canonical version 2 definitions, discovery/corpus foundations, fee/stream contracts, authentication, persistent reviews and mutation APIs, catalog filtering, read-only frontend screens, tracing, and historical hosted CI evidence.
Do not restart those foundation tasks based on old handoff instructions.
Local uncommitted Polymarket US work adds recordings, discovery/books, World Series candidates, venue registration/API metadata, and browser venue panels.
It is not a completed US evaluation release.

1. Finish the existing Kalshi/Polymarket US discovery milestone with running worker/API/PostgreSQL and desktop/mobile validation.
2. Complete source/exception evidence and account/product eligibility for a supported US pair, with human settlement review.
3. Complete US venue fees and automatic sizing integration alongside authenticated browser review actions.
4. Add immediate quote rechecks and a seeded PostgreSQL browser review-to-estimate workflow.
5. Complete counterpart pagination and frontend catalog-wide filtering, then assess additional US venues/categories.
6. Run the forward paper study and finish monitoring, staging, and recovery validation.

Backend review APIs and approval consumption already exist, so frontend review UI work is no longer blocked on their original absence.
Automatic fees, US eligibility, and real-pair evidence still block actionable estimates.
A positive opportunity is not required; conflict, unavailable access, and unprofitable results must remain visible.
Keep focused PR boundaries and check GitHub ownership before overlapping implementation work.

## Current workstream handoffs

| Workstream | Current handoff | Next work |
| --- | --- | --- |
| Integrated product | [Project status](project-status-handoff.md) | Validate and finish the current US discovery baseline |
| Backend | [Backend](backend-handoff.md) | Evidence/eligibility gates and fee-aware, rechecked evaluation |
| Frontend | [Frontend](frontend-handoff.md) | US browser validation, authenticated reviews, complete comparisons/filters |
| Data | [Data](data-handoff.md) | Complete US rulebook/clarification and exceptional-settlement evidence |
| Catalog | [Catalog](catalog-handoff.md) | Full counterpart pagination and API-backed browser filtering |
| Fees | [Fees](fees-handoff.md) | Tested Kalshi/US policies and automatic sizing integration |
| Authentication | [Authentication](auth-handoff.md) | Browser identity/session and real provider validation |
| Streams | [Streams](backend-streams-handoff.md), [live data](live-data-handoff.md) | Fresh US quotes, quote rechecks, eligible venue event publication |
| CI | [CI](backend-ci-handoff.md) | Hosted checks for the exact finished US milestone head |
| Observability | [Tracing](backend-tracing-handoff.md) | Worker metrics/alerts and real collector validation |
| US expansion | [US venues](us-expansion-handoff.md) | Finish discovery capability assessment before another venue |
| Research | [Research](research-handoff.md) | Real-pair evidence first, then the seven-day paper study |

Prior PR/branch instructions and validation records are retained under [history](history/README.md).
The published issue tables below preserve original scope, dependency keys, and proposed file ownership; they are not a current ready-work queue.
Negative-risk support remains excluded, and execution-readiness does not authorize orders, custody, or transfers.

## Published issue scopes and original dependencies

Primary paths identify ownership; each issue separately names necessary integration edits.
Paths that do not exist yet are proposed modules to create.
Shared-file changes require coordination rather than duplicate implementations.
See [CONTRIBUTING.md](../../CONTRIBUTING.md) for PR boundaries, shared integration points and validation.

### Matching

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [C01 #1](https://github.com/acheng2007/arbbot/issues/1) | Version canonical measurement and settlement definitions | None | `backend/arbbot/matching/contracts.py`<br>`backend/tests/test_contract_vocabulary.py` |
| [M01 #7](https://github.com/acheng2007/arbbot/issues/7) | Extract Kalshi definitions from enriched real rules | [#1](https://github.com/acheng2007/arbbot/issues/1), [#3](https://github.com/acheng2007/arbbot/issues/3) | `backend/arbbot/matching/parsers/kalshi.py`<br>`backend/tests/test_kalshi_extraction.py` |
| [M02 #8](https://github.com/acheng2007/arbbot/issues/8) | Extract Polymarket definitions from enriched real rules | [#1](https://github.com/acheng2007/arbbot/issues/1), [#4](https://github.com/acheng2007/arbbot/issues/4) | `backend/arbbot/matching/parsers/polymarket.py`<br>`backend/tests/test_polymarket_extraction.py` |
| [M03 #9](https://github.com/acheng2007/arbbot/issues/9) | Evaluate structured LLM extraction offline | [#6](https://github.com/acheng2007/arbbot/issues/6), [#7](https://github.com/acheng2007/arbbot/issues/7), [#8](https://github.com/acheng2007/arbbot/issues/8) | `backend/arbbot/matching/llm_eval/`<br>`backend/tests/test_llm_output_validation.py`<br>`docs/llm-extraction-evaluation.md` |

### Data

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [D01 #2](https://github.com/acheng2007/arbbot/issues/2) | Persist immutable settlement source artifacts | None | `backend/arbbot/sources/models.py`<br>`backend/arbbot/sources/repository.py`<br>`backend/tests/test_source_artifacts.py` |
| [D02 #3](https://github.com/acheng2007/arbbot/issues/3) | Enrich Kalshi contracts with series and resolution-source evidence | [#2](https://github.com/acheng2007/arbbot/issues/2) | `backend/arbbot/exchanges/kalshi_sources.py`<br>`backend/tests/test_kalshi_sources.py`<br>`backend/tests/fixtures/kalshi_sources/` |
| [D03 #4](https://github.com/acheng2007/arbbot/issues/4) | Capture Polymarket resolution-source and supplemental rule evidence | [#2](https://github.com/acheng2007/arbbot/issues/2) | `backend/arbbot/exchanges/polymarket_sources.py`<br>`backend/tests/test_polymarket_sources.py`<br>`backend/tests/fixtures/polymarket_sources/` |
| [D04 #5](https://github.com/acheng2007/arbbot/issues/5) | Discover overlapping supported event families | [#3](https://github.com/acheng2007/arbbot/issues/3), [#4](https://github.com/acheng2007/arbbot/issues/4) | `backend/arbbot/discovery/service.py`<br>`backend/arbbot/discovery/models.py`<br>`backend/tests/test_targeted_discovery.py` |
| [D05 #6](https://github.com/acheng2007/arbbot/issues/6) | Add labeled supported cross-exchange contract pairs | [#5](https://github.com/acheng2007/arbbot/issues/5), [#1](https://github.com/acheng2007/arbbot/issues/1) | `backend/tests/fixtures/cross_exchange/`<br>`backend/tests/test_cross_exchange_corpus.py`<br>`docs/corpus-cross-exchange.md` |

### Arbitrage

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [A01 #10](https://github.com/acheng2007/arbbot/issues/10) | Validate exceptional settlement scenarios and review completeness | [#1](https://github.com/acheng2007/arbbot/issues/1), [#6](https://github.com/acheng2007/arbbot/issues/6) | `backend/arbbot/arbitrage/settlement.py`<br>`backend/tests/test_settlement_scenarios.py` |
| [F01 #11](https://github.com/acheng2007/arbbot/issues/11) | Define a versioned fee quote interface | None | `backend/arbbot/fees/models.py`<br>`backend/arbbot/fees/base.py`<br>`backend/tests/test_fee_contract.py` |
| [F02 #12](https://github.com/acheng2007/arbbot/issues/12) | Implement Kalshi fee metadata and calculations | [#11](https://github.com/acheng2007/arbbot/issues/11) | `backend/arbbot/fees/kalshi.py`<br>`backend/tests/test_kalshi_fees.py`<br>`backend/tests/fixtures/kalshi_fees/` |
| [F03 #13](https://github.com/acheng2007/arbbot/issues/13) | Implement Polymarket fee metadata and calculations | [#11](https://github.com/acheng2007/arbbot/issues/11) | `backend/arbbot/fees/polymarket.py`<br>`backend/tests/test_polymarket_fees.py`<br>`backend/tests/fixtures/polymarket_fees/` |
| [F04 #14](https://github.com/acheng2007/arbbot/issues/14) | Integrate automatic fee quotes into opportunity sizing | [#12](https://github.com/acheng2007/arbbot/issues/12), [#13](https://github.com/acheng2007/arbbot/issues/13) | `backend/arbbot/arbitrage/engine.py`<br>`backend/tests/test_fee_evaluation.py` |
| [F05 #15](https://github.com/acheng2007/arbbot/issues/15) | Model depth impact and configurable execution slippage conservatively | [#14](https://github.com/acheng2007/arbbot/issues/14) | `backend/arbbot/arbitrage/slippage.py`<br>`backend/tests/test_slippage_evaluation.py` |
| [L05 #31](https://github.com/acheng2007/arbbot/issues/31) | Revalidate opportunity quotes before actionable presentation | [#30](https://github.com/acheng2007/arbbot/issues/30), [#15](https://github.com/acheng2007/arbbot/issues/15), [#19](https://github.com/acheng2007/arbbot/issues/19) | `backend/arbbot/arbitrage/revalidation.py`<br>`backend/tests/test_opportunity_revalidation.py` |

### Backend

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [R01 #16](https://github.com/acheng2007/arbbot/issues/16) | Persist versioned definition drafts and human reviews | [#1](https://github.com/acheng2007/arbbot/issues/1), [#2](https://github.com/acheng2007/arbbot/issues/2) | `backend/arbbot/reviews/models.py`<br>`backend/arbbot/reviews/repository.py`<br>`backend/tests/test_review_repository.py` |
| [R02 #17](https://github.com/acheng2007/arbbot/issues/17) | Add authentication and reviewer authorization | None | `backend/arbbot/auth/`<br>`backend/tests/test_auth.py`<br>`docs/authentication.md` |
| [R03 #18](https://github.com/acheng2007/arbbot/issues/18) | Expose authenticated review and draft APIs | [#16](https://github.com/acheng2007/arbbot/issues/16), [#17](https://github.com/acheng2007/arbbot/issues/17), [#10](https://github.com/acheng2007/arbbot/issues/10) | `backend/arbbot/api/routes/reviews.py`<br>`backend/tests/test_review_api.py` |
| [R04 #19](https://github.com/acheng2007/arbbot/issues/19) | Use database approvals in the ingestion and evaluation pipeline | [#18](https://github.com/acheng2007/arbbot/issues/18), [#10](https://github.com/acheng2007/arbbot/issues/10) | `backend/arbbot/reviews/provider.py`<br>`backend/tests/test_review_pipeline.py` |
| [B01 #20](https://github.com/acheng2007/arbbot/issues/20) | Add market and match search and filtering | None | `backend/arbbot/api/routes/catalog.py`<br>`backend/arbbot/storage/catalog_queries.py`<br>`backend/tests/test_catalog_queries.py` |

### Frontend

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [W01 #21](https://github.com/acheng2007/arbbot/issues/21) | Scaffold the Next.js application and shared UI foundation | None | `apps/web/package.json`<br>`apps/web/`<br>`apps/web/package-lock.json` |
| [W02 #22](https://github.com/acheng2007/arbbot/issues/22) | Generate the typed API client and shared data access layer | [#21](https://github.com/acheng2007/arbbot/issues/21) | `apps/web/src/lib/api/`<br>`apps/web/src/lib/query/`<br>`apps/web/scripts/generate-api.*` |
| [W03 #23](https://github.com/acheng2007/arbbot/issues/23) | Build the market browser and source detail screen | [#22](https://github.com/acheng2007/arbbot/issues/22), [#20](https://github.com/acheng2007/arbbot/issues/20) | `apps/web/src/features/markets/`<br>`apps/web/src/app/markets/`<br>`apps/web/tests/markets/` |
| [W04 #24](https://github.com/acheng2007/arbbot/issues/24) | Build the read-only contract comparison screen | [#22](https://github.com/acheng2007/arbbot/issues/22) | `apps/web/src/features/comparisons/`<br>`apps/web/src/app/matches/`<br>`apps/web/tests/comparisons/` |
| [W05 #25](https://github.com/acheng2007/arbbot/issues/25) | Build authenticated draft editing and review actions | [#24](https://github.com/acheng2007/arbbot/issues/24), [#18](https://github.com/acheng2007/arbbot/issues/18), [#19](https://github.com/acheng2007/arbbot/issues/19) | `apps/web/src/features/reviews/`<br>`apps/web/src/app/reviews/`<br>`apps/web/tests/reviews/` |
| [W06 #26](https://github.com/acheng2007/arbbot/issues/26) | Build the opportunity dashboard with live status | [#22](https://github.com/acheng2007/arbbot/issues/22), [#15](https://github.com/acheng2007/arbbot/issues/15) | `apps/web/src/features/opportunities/`<br>`apps/web/src/app/opportunities/`<br>`apps/web/tests/opportunities/` |

### Live data

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [L01 #27](https://github.com/acheng2007/arbbot/issues/27) | Define order-book stream and resynchronization contracts | None | `backend/arbbot/streams/models.py`<br>`backend/arbbot/streams/base.py`<br>`backend/tests/test_stream_contract.py` |
| [L02 #28](https://github.com/acheng2007/arbbot/issues/28) | Implement Kalshi order-book streaming | [#27](https://github.com/acheng2007/arbbot/issues/27) | `backend/arbbot/streams/kalshi.py`<br>`backend/tests/test_kalshi_stream.py`<br>`backend/tests/fixtures/kalshi_stream/` |
| [L03 #29](https://github.com/acheng2007/arbbot/issues/29) | Implement Polymarket order-book streaming | [#27](https://github.com/acheng2007/arbbot/issues/27) | `backend/arbbot/streams/polymarket.py`<br>`backend/tests/test_polymarket_stream.py`<br>`backend/tests/fixtures/polymarket_stream/` |
| [L04 #30](https://github.com/acheng2007/arbbot/issues/30) | Integrate streams with worker lifecycle and health | [#28](https://github.com/acheng2007/arbbot/issues/28), [#29](https://github.com/acheng2007/arbbot/issues/29) | `backend/arbbot/ingestion/live_books.py`<br>`backend/tests/test_live_book_pipeline.py` |

### Infrastructure

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [Q01 #32](https://github.com/acheng2007/arbbot/issues/32) | Verify the first hosted backend CI run | None | `.github/workflows/backend.yml`<br>`docs/ci.md` |

### QA

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [Q02 #33](https://github.com/acheng2007/arbbot/issues/33) | Add frontend CI and the full review-to-opportunity browser test | [#23](https://github.com/acheng2007/arbbot/issues/23), [#25](https://github.com/acheng2007/arbbot/issues/25), [#26](https://github.com/acheng2007/arbbot/issues/26), [#32](https://github.com/acheng2007/arbbot/issues/32) | `.github/workflows/frontend.yml`<br>`apps/web/e2e/`<br>`infra/test/` |

### Observability

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [O01 #34](https://github.com/acheng2007/arbbot/issues/34) | Expose worker health and ingestion metrics | [#30](https://github.com/acheng2007/arbbot/issues/30) | `backend/arbbot/observability/worker_metrics.py`<br>`backend/tests/test_worker_metrics.py` |
| [O02 #35](https://github.com/acheng2007/arbbot/issues/35) | Add dashboards and alert rules for feed and worker failures | [#34](https://github.com/acheng2007/arbbot/issues/34) | `infra/observability/`<br>`docs/observability.md` |
| [O03 #36](https://github.com/acheng2007/arbbot/issues/36) | Add tracing across ingestion evaluation and API requests | None | `backend/arbbot/observability/tracing.py`<br>`backend/tests/test_tracing.py` |

### Deployment

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [P01 #37](https://github.com/acheng2007/arbbot/issues/37) | Add a reproducible staging deployment and secret configuration | [#17](https://github.com/acheng2007/arbbot/issues/17), [#19](https://github.com/acheng2007/arbbot/issues/19), [#30](https://github.com/acheng2007/arbbot/issues/30), [#33](https://github.com/acheng2007/arbbot/issues/33), [#35](https://github.com/acheng2007/arbbot/issues/35) | `infra/deploy/`<br>`docs/deployment.md` |

### Operations

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [P02 #38](https://github.com/acheng2007/arbbot/issues/38) | Document and rehearse database backup and recovery | [#37](https://github.com/acheng2007/arbbot/issues/37) | `infra/recovery/`<br>`docs/recovery.md` |

### Research

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [X01 #39](https://github.com/acheng2007/arbbot/issues/39) | Assess negative-risk market support without enabling it | None | `docs/decisions/negative-risk.md`<br>`backend/tests/fixtures/negative_risk/` |

### Deferred

| Issue | Task | Depends on | Primary files |
| --- | --- | --- | --- |
| [X02 #40](https://github.com/acheng2007/arbbot/issues/40) | Specify venue access and balance checks if execution is authorized | Owner authorization; deferred | `docs/decisions/execution-readiness.md` |

## Fees and slippage

Issues #11 through #15 implement the fee contract, venue fee policies, engine integration and execution-slippage model in dependency order.
Issue #15 must verify that fees, deeper book levels, rounding or adverse movement can independently or jointly eliminate an apparent arbitrage.
Actual depth cost accounts for price impact; a separate allowance covers adverse movement without double-counting spread or depth.
The dashboard and revalidation issues depend on this completed cost model.

## Parallel work and shared edits

Frontend bootstrap, authentication, source storage, fee/stream interfaces, and canonical definitions are already implemented at their documented scopes.
The original dependency graph remains useful for identifying integration contracts, not for restarting completed work.
Venue-specific fetchers, parsers, fee implementations and stream adapters use separate modules and test files.
Feature screens live in separate frontend feature and route directories.
Small necessary edits to shared routers, worker wiring, config, schemas, engine or migrations are explicitly called out in the issue.
Coordinate those edits and serialize their merges rather than treating a whole shared file as permanently off limits.

## Maintenance

`backlog.json` preserves issue scope and dependency keys.
`issues.json` maps those keys to published GitHub issues.
When scope changes, update the affected issue and this index together.
Do not regenerate or republish issues blindly; preserve existing issue numbers and discussion.
