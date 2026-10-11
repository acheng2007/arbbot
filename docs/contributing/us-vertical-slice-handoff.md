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
The production webpack build passed; Turbopack hit an internal port-binding failure.

## Remaining stages and next action

Stages 3 through 7 and the complete recorded-exchange/OIDC acceptance harness remain outstanding.
Current official US documentation was retrieved on October 11, including the October 7 fee schedule.
Do not use October 1 fee recordings as current policy.
The browsing connector returned an invalidated OAuth token; official documents were retrieved directly over HTTPS instead.

Next action: capture applicable official US settlement documents and expose bounded, artifact-linked derived text for human review (Stage 3).
Keep live evaluation blocked until settlement, source, access, and fee gates pass.

## Stage 2: broad catalog inventory

Added immutable raw observations, current inclusion/exclusion projections, and durable cursor/offset progress in additive migration `b021_us_catalog_inventory`.
The migration follows the actual `b016_review_revisions` head; numbering alone is not migration order.
Pages and continuation commit atomically; repeated pages stop without skipping forward.
Broad discovery is enabled in Compose and the live demo environment; focused family discovery remains configurable.
The persisted catalog is independent of the bounded quote set, which prioritizes verified pairs and watchlists and rotates other candidates with a durable offset.
Matching reads the fresh catalog rather than only monitored books.
Indexed structured-event and title candidate retrieval bounds unfamiliar hypotheses and exposes retrieval limits.
The public `/api/v1/catalog/inventory` endpoint exposes raw exclusions and observation identities with pagination.
US normalization now validates documented binary formats, instrument orientation, USD units, and numeric constraints independently of sports categories.
Unfamiliar formats remain excluded; optional typed instrument/native-direction fields preserve historical payload readability and invalidate changed settlement terms.

Current public smoke checks fetched US catalog data and executable books from both venues.
The observed sample contained sports instruments; election normalization is covered by structural tests, not claimed as a complete live election audit.
Kalshi REST books still have no source timestamp and report that limitation explicitly.
No positive live opportunity was manufactured, and US evaluation remains blocked.
The full SQLite and PostgreSQL suites each passed (446 tests).
The new inventory API normalizes SQLite receipt timestamps to UTC.
Real public pages were persisted in PostgreSQL with continuation tokens and explicit exclusions; no fixed live count was asserted.
Migration roundtrip tests preserve existing markets, snapshots, reviews, and source evidence.
Use `.venv/bin/python backend/scripts/smoke_us.py` for opt-in public catalog/book checks.
The script does not validate completed source, fee, access, approval, or evaluation gates.
