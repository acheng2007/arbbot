# Frontend workstream handoff

## Current status: October 11, 2026

Branch: `backend/completion`; no PR was opened or remote status rechecked during this cleanup.
This update reconciles the local implementation and documented delivery evidence.
See the [roadmap](../implementation-roadmap.md) for the integrated sequence and the [project status handoff](project-status-handoff.md) for the October 11 checks and limitations.
Prior session details and validation evidence are preserved in [history](history/frontend-handoff.md).

## Completed

Next.js foundations, exact-string generated API contracts, same-origin reads, market/source screens, read-only comparisons, and opportunity dashboard/detail screens are implemented.
The opportunity UI includes reviewed costs, settlement scenarios, freshness, blocked states, and SSE reconnect handling.
Existing screens have unit tests, fixture-backed desktop/mobile Playwright coverage, prior visual inspection, and historical live-price smoke evidence.
The frontend CI definition and historical successful fixture-backed hosted CI evidence exist.
Local uncommitted US work adds venue API-driven selection/panels and distinct US price/access labels.

## Remaining work and dependencies

Authenticated draft editing, approval, rejection, revocation, and conflict handling remain unfinished.
Backend authentication, draft/review APIs, and worker approval consumption are already implemented; their former absence is no longer the blocker for review UI work.
Browser identity/session integration and a seeded PostgreSQL full-workflow test remain required.
The market browser loads only 200 matches, selects one pair per market, and applies search/status filters only to the loaded page despite backend filtering support.
US evaluation presentation depends on complete rules, eligibility, automatic fees, and immediate quote rechecks.

## Next action

Validate the existing US desktop/mobile quote/comparison UI against the restored running stack, then build authenticated review actions against the existing API with evidence requirements and concurrent-edit conflicts preserved.

## October 11 snapshot integration update

Branch: `backend/completion`.
Browser and fixture streams now use backend `snapshot` events; current opportunity/evaluation/history queries refresh on delivery.
Connectivity labels no longer assert quote freshness.
Desktop/mobile opportunity Playwright passed (18 tests), frontend unit tests passed (57), and type/lint/generated-client checks passed.
The actual PostgreSQL/worker/API/Next.js simulation workflow refreshed on both viewports; screenshots were inspected.
Next action: continue the US vertical slice with durable broad catalog inventory, then evidence-linked review workflows.
See [the implementation handoff](us-vertical-slice-handoff.md) for remaining stages.

## October 11 captured source text update

Source terms now expose captured document text in collapsible plain-text panels and display unresolved evidence gaps.
Real captured US rulebook evidence was inspected in desktop/mobile browsers with no horizontal overflow.
Next action: implement evidence-linked review editing and OIDC sessions after product-document applicability and review validation are ready.

## October 11 counterpart browsing update

Comparison details load exact pair and contract identities beyond the first catalog page.
Markets expose paginated counterparts, including multiple pairs for the same market.
Desktop/mobile regression tests verify browsing beyond 200 pairs without horizontal overflow.
Next action: implement the Stage 5 OIDC and evidence-linked review editor against the existing revision-aware review APIs.
See [the vertical slice handoff](us-vertical-slice-handoff.md) for the joint-outcome schema and remaining blockers.

## October 11 interactive demo

The user requested a test demo; simulation is running at `http://127.0.0.1:3000/opportunities` and real Kalshi/US discovery at `http://127.0.0.1:3001/markets`.
Desktop/mobile checks passed for simulation calculations, SSE refresh, real paired price refresh, and incomplete settlement/source labels.
Screenshots are under `apps/web/test-results/test-demo-*.png`.
The services are left running for inspection; see the vertical slice handoff for runtime details and session IDs.
Next action: walk through the simulation calculation, then inspect the live Dodgers comparison before resuming Stage 5 implementation.

## October 11 broader live demo

Removed the two-contract runtime watchlist from the live demo at `http://127.0.0.1:3001/markets`.
More than 1,000 supported venue contracts were discovered during verification, with quote monitoring bounded separately to 20 per venue.
Desktop/mobile checks passed for multiple contracts, pagination, and venue filtering without overflow.
Next action: refresh the live demo and explore catalog pages; implementation then resumes at Stage 5.

## Integrated workflow implementation follow-up

Catalog-wide lightweight summaries now drive market browsing with API search, status, category, and venue filters.
Comparison lists paginate and load contracts by exact ID.
Cards resolve counterparts by market ID, and opportunity details resolve exact opportunity IDs.
Blocked evaluations expose status and signed calculations; native US short actions and collateral breakdowns are displayed.
Snapshot refresh covers catalog, comparisons, evaluations, opportunities, books, and status.
The gross settlement payout table label was corrected during visual review.
See [the integrated workflow handoff](arbitrage-workflow-handoff.md) for validation and remaining acceptance work.
Next action: run the recorded PostgreSQL / worker / API / browser harness and verify US native short, signed-loss, withdrawal, and recovery states on desktop and mobile.

## October 12 paused checkpoint

Work is paused at the user's request.
The recorded PostgreSQL / worker / API / Next.js acceptance passed, including both desktop/mobile tests.
The latest PostgreSQL suite passed 496 tests; SQLite has one unresolved evaluation-history scheduling test failure.
See [the integrated workflow handoff](arbitrage-workflow-handoff.md) for saved implementation, exact verification status, and artifacts.
Next action: reproduce and resolve the SQLite scheduling-history failure before resuming final acceptance review.

## October 12 completed integrated workflow

This supersedes the paused checkpoint.
The requested Kalshi / Polymarket US workflow and full recorded acceptance passed.
SQLite and PostgreSQL each passed 497 tests; frontend units passed 58, fixture browsers passed 50, and connected desktop/mobile browsers passed four.
Type, lint, generated-contract, migration preservation, financial, and production build checks passed.
The final UI fixes preserve opportunity navigation across refreshes, coalesce pending SSE-triggered reads, wrap mobile reviewer identifiers, and separate actual US fee policy snapshots from legacy review costs.
Branch: `backend/completion`; no PR or push.
See [the integrated workflow handoff](arbitrage-workflow-handoff.md) for artifacts, operational limits, and the live evidence observations.
Next action: inspect the completed acceptance artifacts and prepare the first real candidate's reviewed evidence package using the operator CLI.

Exact historical opportunity details now show current invalidation reasons, including changed quotes, reviews, sources, access, fees, and venue health.

## October 14 advisory classification workflow

Branch: `backend/completion`; no PR or push.
Comparison lists and details now distinguish AI event suggestions from established event evidence and reviewed verification.
They display clause findings, captured quotations, model confidence/probability scores, coverage limitations, lifecycle states, and recorded-response labels.
Classification filtering uses the paginated backend API; snapshot updates refresh advice.
Withdrawn AI-only pairs retain readable stale advice through the classification endpoint.
OpenAPI and TypeScript contracts were regenerated.
Visual inspection corrected hidden skip-link capture artifacts without removing keyboard access and improved quotation-caption wrapping.
Frontend units passed 65, fixture browsers passed 56, and connected desktop/mobile browsers passed six.
Type, lint, generated-contract, and webpack production-build checks passed.
See [the Jev handoff](jev-handoff.md) for worker/storage validation, artifacts, benchmark coverage, and the absent live key.
Next action: configure the backend OpenRouter key and run the documented live benchmark before assessing model quality.


## October 14 market dashboard redesign

Branch: `backend/completion`; no PR or push.
The home route now opens the paired-market dashboard.
The frontend uses a light horizontal navigation shell, green price accents, compact market cards, and responsive layouts.
Paired markets and All markets have shareable URL state with catalog-wide search, venue, status, category, and pagination controls.
The matches API gained optional same-event, rejection-exclusion, category, and market-status filters applied before pagination, including revalidated reviews.
OpenAPI and the generated TypeScript client were updated.
Market cards display aligned venue asks, depth at the best price, quote freshness, review status, and explicit US short-collateral labels.
Mixed recording origins and unsupported instruments remain visible.
Opportunity summaries show event, directions, estimated net result, return, capital, and size without detailed fee or audit data.
Calculations, settlement scenarios, AI rationale, source documents, review evidence, and diagnostics are expandable.
Blocked evaluations, history, and extracted evidence load on demand.
Connection, stale-data, simulation, missing-depth, and invalidation states remain explicit.
An outdated connection-page message claiming market data was absent was also corrected.

### Validation

Playwright MCP inspected the original interface and Kalshi reference, then the redesigned desktop and mobile dashboard, comparisons, and opportunity screens.
The original interface was reproduced using recorded fixtures because the previously documented live demo servers were unavailable.
The first paired card's four prices fit within the 1440x900 desktop and 390x844 mobile viewports.
The complete fixture browser suite passed 62 tests; the final dashboard suite passed 10 tests, including four added US-label and unverified-pair cases.
Frontend unit tests passed 66 tests.
Type checking, lint, generated-client drift checks, the webpack production build, backend Ruff checks, and whitespace checks passed.
The backend catalog, API, and classification suite passed 52 tests against the local test database.
Connected PostgreSQL/worker acceptance tests were adapted to the expandable interface but were not rerun in this redesign session.
No live exchange behavior or financial calculation logic was changed.
Screenshots and browser traces remain local inspection artifacts rather than committed application assets.
Unrelated staged research and untracked fee work were preserved.

### Next action

Run the redesigned paired dashboard against the live Kalshi/Polymarket US stack and inspect real counterpart coverage and quote-health states on desktop and mobile.

## October 14 backend automatic qualification compatibility

Branch: `backend/completion`.
Generated contracts include automatic assessment summaries, settlement models, optional human reviews, separate potential APIs, and optional veto clearing.
Existing match badges identify automatic qualification accurately, and opportunity details tolerate a missing human review.
The user selected backend/API implementation only, so no new potential-opportunity view or qualification inspection flow was implemented.
See [the backend automatic qualification handoff](automatic-qualification-handoff.md) for API semantics and source-coverage limits.
Next action: when frontend work is requested, add separate potential and qualified result views using the new APIs without mixing ordinary-outcome spread with qualified worst-case estimates.

## October 15 consolidation validation

Branch: `main`; consolidation PR [#57](https://github.com/acheng2007/arbbot/pull/57) is merged.
Hosted validation reproduced a mobile evidence-test race: the test clicked Review evidence on the old opportunity route before comparison navigation completed.
The downloaded trace and screenshot were inspected before editing.
The assertion now waits for the destination URL and comparison-only navigation link, then opens the destination disclosure.
No UI behavior, evidence assertions, or timeout limits were changed.
The corrected scenario passed ten local desktop/mobile repetitions with two concurrent workers.
The final hosted frontend run passed all 66 desktop/mobile tests, 66 unit tests, generated-client/type/lint checks, and the production build.
All completed branches were retained in main and removed; see [the consolidation handoff](branch-consolidation-handoff.md).
Next action: when frontend work is requested, implement separate potential and qualified views against the existing APIs, preserving the current evidence and assumption boundaries.

## Accepted suggestion-visibility direction

Branch: `main`; documentation decision only.
The user approved [candidate visibility with independent automatic verification](../decisions/candidate-visibility.md).
Display valid current Jev same-event suggestions as Unverified regardless of their model scores; use scores for ordering and explanation.
Distinguish Verified settlement relationships, explicit Mismatch, stale/history, and separately gated arbitrage estimates.
The current score-based eligibility and established-event-only paired filtering still require implementation changes; do not document them as delivered.
Next action: integrate the accepted policy with backend eligibility/filtering and connected desktop/mobile checks, including a low-score suggestion that remains visible while settlement evidence is incomplete.

## October 15 broad discovery workflow

The integrated broad-discovery implementation is on `feature/broad-discovery-workflow`.
See [the broad-discovery handoff](broad-discovery-handoff.md) for delivered workflow, validation, model benchmark, and limitations.
Next action: run a sustained live Kalshi/US coverage study across categories, then prioritize authentic source-applicability and settlement-language extensions from its blocker distribution.
