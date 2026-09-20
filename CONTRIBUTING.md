# Contributing

Start with the [implementation roadmap](docs/implementation-roadmap.md) and [contributor issue index](docs/contributing/README.md).
The issue index separates ready work from dependency-blocked work and identifies the primary file ownership for each PR.
New paths listed in issues are proposed module boundaries, not claims that those files already exist.

## One issue, one pull request

Claim an issue by commenting with your intended scope before starting.
Open one PR for one issue and reference it with `Closes #number`.
Do not bundle adjacent features, global formatting, dependency upgrades, or opportunistic refactors into the same PR.
If an issue proves too large, propose a smaller interface-preserving split before implementation.
Keep incomplete dependent features out of a supposedly standalone PR.

Dependencies must be merged before implementation relies on them.
A draft PR may use an explicit agreed interface earlier, but it must be independently testable before merge.
Read-only frontend work can proceed beside backend data work once the web foundation and typed client land.
Do not invent missing API response fields to unblock a screen.

## File ownership and necessary integration changes

Each issue lists its primary module/test files and permitted integration changes.
Keep edits within those paths unless a concrete dependency makes an outside change necessary.
List every outside-scope file in the PR with its reason and notify the affected issue owner before overlapping work.
Prefer new feature modules, route modules, repositories and focused test files to enlarging shared files.
This is coordination guidance, not a requirement to duplicate code or avoid a necessary correctness fix.

Treat these as shared integration points:

- `backend/arbbot/domain.py`, `config.py`, `api/app.py`, and `ingestion/pipeline.py`.
- `backend/arbbot/arbitrage/engine.py`, storage model registration, and the Alembic revision graph.
- `docs/openapi.json`, `docs/definitions.schema.json`, and `docs/reviews.schema.json`.
- Frontend package manifests/lockfiles, application layout/providers, generated client and workflow files.

Coordinate shared edits in the issue before starting and serialize merges when they touch the same interface.
Regenerate API artifacts in the PR that changes their source contract; never hand-edit generated files.
Keep generated frontend client refreshes in a dedicated reproducible change when no consumer change is required.
Use one additive migration per schema change and rebase its parent against current main before merge.
Do not rewrite migrations already applied by others.
Put parser fixtures in venue/feature directories rather than rewriting the initial corpus.

## Contracts and correctness

An event match does not prove equivalent settlement.
Missing evidence, unsupported instruments and unresolved exceptional outcomes must remain unverified.
All financial arithmetic uses Decimal or exact integers in the backend; APIs retain decimal strings.
Net opportunity profit must account for executable depth, market-specific fees, rounding and execution-slippage allowance.
Slippage allowances do not guarantee fills or make cross-exchange purchases atomic.
No issue in this backlog authorizes orders, custody or transfers.

## Validation

Follow [AGENTS.md](AGENTS.md) and the setup/test commands in [README.md](README.md).
Use focused tests for the changed module and the relevant integration path.
For reported bugs, reproduce through the user-facing path before editing; document any limitation.
Backend changes run lint/format checks and the relevant SQLite/PostgreSQL suite.
Schema changes run migration checks and regenerate affected schemas.
Frontend changes include accessible loading, empty, error and stale states and browser/visual verification.
Do not use live exchange services or paid model calls in default CI tests.
Never claim a hosted CI run passed based only on local tests.
