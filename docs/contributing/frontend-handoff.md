# Frontend workstream handoff

The user requested that all frontend issues be picked up on a separate branch and continued in a new chat.
Issues #21 through #26 and frontend QA issue #33 are assigned to `acheng2007`.
Issue #21 is implemented on `frontend/21-web-foundation`; see the current delivery section below.

## Workspace and branch

Repository: `/Users/adam/Project/arbbot`.
Workstream branch: `frontend/workstream`, created from main at `03b91c2`.
Read `AGENTS.md`, `CONTRIBUTING.md`, `docs/contributing/README.md`, and the current GitHub issue before editing.
GitHub repository: https://github.com/acheng2007/arbbot.

Use this branch as the frontend workstream starting point.
Preserve the user's one-issue-per-PR requirement: create focused issue branches from the appropriate merged baseline, or explicitly stacked branches with a clear dependency base.
Do not open one PR containing all frontend issues.
Do not merge unreviewed issue branches into main.
Keep commits focused and use only the user's configured Git identity.

## First task

Start with [#21](https://github.com/acheng2007/arbbot/issues/21): scaffold the Next.js application and shared UI foundation.
Use Next.js, React, TypeScript, Tailwind, shadcn/ui, TanStack Query/Table, Vitest and Playwright as specified in AGENTS.md.
Design can proceed while backend source enrichment is underway.
Default feature ownership is `apps/web/`; explain any necessary backend or shared-file edits.
Select and verify dependency versions at implementation time.

## Issue sequence

| Issue | Work | Dependencies |
| --- | --- | --- |
| #21 | Application scaffold, layout and shared components | None |
| #22 | Generated typed API client and data access | #21 |
| #24 | Read-only comparison screen | #22 |
| #23 | Market browser and source details | #22 and backend filtering #20 |
| #25 | Authenticated draft editing and reviews | #24 and backend #18, #19 |
| #26 | Opportunity dashboard | #22 and fee/slippage integration #15 |
| #33 | Frontend CI and full browser workflow | #23, #25, #26 and hosted backend CI #32 |

Design and explicitly labeled mock states can advance before backend dependencies are complete.
Do not claim a blocked issue is complete, invent backend response fields, or treat mock approval as a real approval.
Keep mocks behind interfaces compatible with real API contracts.
Read-only screens can integrate existing endpoints immediately where their contracts suffice.

## Available backend contracts

FastAPI exposes markets, books, extraction drafts, matches, opportunities, audit history, health, and SSE.
`docs/openapi.json` is the committed schema for generating client types.
The local Docker configuration defaults to simulation and serves the API at `http://localhost:8000` when running.
Backend tests last passed with 75 tests on SQLite and PostgreSQL; do not assume a hosted CI run passed without checking.
Review mutations, authentication, advanced filtering and automated fee integration remain dependent issues.

## Required UX and financial presentation

Present simulation/live, loading, empty, missing evidence, conflicting rules, unverified candidates, stale prices, errors and reconnect states explicitly.
Keep financial calculations in the backend and preserve decimal strings in the browser.
Show fees, executable depth costs and slippage allowance separately, with net profit after all costs.
A quote-supported estimate is not a guaranteed profit or an atomic cross-exchange fill.
No trade execution, custody or transfers are in scope.
Validate responsive layouts, keyboard accessibility, and browser behavior; visually inspect the rendered screens.

## Current delivery: issue #21

Implemented the Next.js foundation with pinned dependencies, responsive navigation, Query provider, shadcn-compatible UI configuration/button, shared loading/error/empty/stale states, and Vitest/Playwright configuration.
The overview is explicitly a preview with no market data or fabricated opportunities.
The connection route reads server-side `BACKEND_URL` and validates the existing `/health/live` response, including simulation/live mode.
No backend or feature-screen implementation is included.

Issue branch: `frontend/21-web-foundation`.
PR base: `frontend/workstream`, including the existing handoff and committed session-handoff instruction baseline at `01ace35`.
Keep this issue as its own PR; do not merge it without review.
Root `.gitignore` and `README.md` changes are the issue-authorized integration changes.
This handoff update is required by the current `AGENTS.md` session instructions.

Validation: lint, typecheck, production build, 10 Vitest checks, and desktop/mobile Chromium navigation checks pass.
Desktop/mobile overview screenshots and the real-backend connection screen were visually inspected.
The real FastAPI service on port 8011 was verified through the browser using a nondefault `BACKEND_URL`.
Browser tests use labeled simulation responses and exercise a failed refresh with stale-state messaging.
No hosted frontend CI claim is made; CI remains issue #33.

Publication status: [PR #43](https://github.com/acheng2007/arbbot/pull/43) is merged into `main`, and issue #21 is closed.

## Current delivery: issues #22, #23, #24, #26

Branch: `frontend/read-only-screens`, targeting `main` now that #21 is merged.
The user asked for as much backend-free frontend as possible and explicitly allowed several issues in one pull request.

Issue #22, generated client and data access.
`apps/web/scripts/generate-api.mjs` generates `src/lib/api/schema.ts` from the committed `docs/openapi.json`.
`openapi-typescript` was rejected because its peer range is TypeScript 5 and this package pins TypeScript 6; the generator has no runtime dependency and fails loudly on any OpenAPI construct it does not model.
`npm run generate:api:check` detects drift and runs inside `npm test`.
Monetary and quantity fields are generated as `DecimalString` and never converted to a number.
The browser calls same-origin routes under `/api/data/[operation]`, which validate the operation against the generated registry and proxy server-side, so `BACKEND_URL` never reaches a browser bundle.
`ApiError` models unreachable, timeout, cancelled, not-found, invalid-request, backend-error and invalid-response cases; TanStack Query supplies the abort signal and cancelled requests are not retried.

Issue #24, read-only comparison screen at `/matches` and `/matches/[matchId]`.
Similarity is labeled a discovery signal everywhere it appears and never a verification state.
Differing and unknown fields sort above agreeing ones, each with the exact source quotation behind both sides.
`same_event: false` shows an explicit statement that a price difference between the two is not arbitrage.
The review panel flags an expired approval and flags reviewed terms hashes that no longer match the published ones.

Issue #23, market browser at `/markets` and source detail at `/markets/[marketId]`.
Venue and pagination are sent to the API; status and text search narrow the loaded page only, and the interface says so, because catalog-wide filtering is backend issue #20.
Filters round-trip through the address bar.
Source detail shows the original rules text, extracted facts with quotations, undetermined fields, and order-book health with source and receipt timestamps kept separate.

Issue #26, opportunity dashboard at `/opportunities` and `/opportunities/[opportunityId]`.
Fees, executable depth cost and slippage allowance are listed separately, with net profit stated as being after all costs.
Payout is shown for every reviewed settlement outcome, alongside execution assumptions and a statement that no order is placed.
`/api/stream` proxies backend Server-Sent Events and serves a fixture stream in fixture mode; a dropped connection states that the figures are no longer confirmed rather than leaving a stale success view.
Evaluations with `blocked_reasons` and expired history entries are both surfaced.

Backend-free development: `ARBBOT_WEB_DATA_SOURCE=fixtures` serves every screen from a recorded dataset typed against the generated schema.
Fixture mode is opt-in and any other value reads the real backend.
Every fixture-served screen carries a banner stating that no exchange or backend was contacted.

Two defects found and fixed during browser testing.
Next 16 returns dynamic route segments still percent-encoded, so market identifiers containing ":" were double-encoded and every market detail page reported "record does not exist"; `src/lib/routing.ts` decodes at the route boundary.
`Intl.DateTimeFormat` threw at module scope because `timeZoneName` cannot combine with `dateStyle`/`timeStyle`.

Out-of-scope fixes, both mentioned as required: the overview page and header no longer describe a disconnected preview and now link to the real screens, and the sidebar navigation scrolls horizontally at mobile widths.

Validation run on this branch: `npm run lint`, `npm run typecheck`, `npm run generate:api:check`, `npm run build`, 55 Vitest checks, and 36 Playwright checks across desktop and mobile Chromium, all passing.
Desktop and mobile screenshots of all ten routes were inspected with no horizontal overflow and no console errors; `e2e/inspect.mjs` reproduces that sweep.
No hosted CI claim is made.

## Not delivered

Issue #25, authenticated draft editing and review actions, is not started.
It depends on backend review mutations and authorization (#18, #19) that do not exist, and mock approvals must not be presented as real approvals.

Issue #33 has partial backend-independent work on `frontend/33-ci-fixtures`.
Hosted backend CI dependency #32 is closed, but the full contract still depends on #25 and requires authenticated review actions against a seeded backend rather than fixtures.

Publication status: `frontend/read-only-screens` is pushed to `origin`.
The GitHub CLI is authenticated as `acheng2007`.

Next action: open `frontend/read-only-screens` into `main` with `Closes #22`, `Closes #23`, `Closes #24`, and `Closes #26` in the body, then open `frontend/33-ci-fixtures` into `frontend/read-only-screens` as partial #33 work without closing the issue.
Issue #25 remains blocked on backend #18 and #19, and the remaining #33 workflow remains blocked on #25.
