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
