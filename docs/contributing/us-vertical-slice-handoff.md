# Kalshi and Polymarket US vertical slice handoff

Branch: `backend/completion`.
No PR opened.

## Stage 1: integration wiring

Reproduced publication suppression through SQLite and PostgreSQL-backed API tests before changing code.
Reproduced the ignored backend `snapshot` event in desktop Playwright before changing code.
Publication now checks enabled venues and healthy exact snapshots per leg, retaining current review validation and historical readability.
A discovery failure now invalidates only opportunities using that venue.
The browser and fixture stream use the backend `snapshot` contract, refreshing opportunity, evaluation, and history queries.
Stream connectivity and snapshot delivery do not assert quote freshness.

Docker Desktop was started and an isolated `arbbot-integration` PostgreSQL service was created.
Existing migrations upgraded successfully against PostgreSQL.
The real PostgreSQL, persistent simulation worker, API, and Next.js workflow refreshed through SSE on desktop and mobile.
Screenshots under `apps/web/test-results/stage1-backend-*.png` were inspected for layout.
Synthetic publication tests prove US venue routing only; live US evaluation remains blocked.

Checks: 15 focused backend tests passed on PostgreSQL; 18 opportunity Playwright tests passed across desktop/mobile; 57 frontend unit tests passed; TypeScript and generated-client drift checks passed.
The full SQLite backend suite passed (433 tests), and frontend lint passed.
The production build is being rerun with local process permissions after the sandbox prevented Turbopack from binding its internal port.

## Remaining stages and next action

Stages 2 through 7 and the complete recorded-exchange/OIDC acceptance harness remain outstanding.
Current official US documentation was retrieved on October 11, including the October 7 fee schedule.
Do not use October 1 fee recordings as current policy.
The browsing connector returned an invalidated OAuth token; official documents were retrieved directly over HTTPS instead.

Next action: implement durable broad catalog continuation and raw observations with a quote-monitoring budget independent of catalog coverage (Stage 2).
Keep live evaluation blocked until settlement, source, access, and fee gates pass.
