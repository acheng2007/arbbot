# Frontend workstream handoff

The user requested that all frontend issues be picked up on a separate branch and continued in a new chat.
Issues #21 through #26 and frontend QA issue #33 are assigned to `acheng2007`.
No frontend implementation has started in this handoff.

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
