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

## Stage 3: captured text foundations and verified US rulebook host

Pinned `pypdf==6.20.0` and added text/HTML/PDF extraction in isolated subprocesses.
Extraction bounds cover 100 pages, 300,000 characters, stream expansion, concurrency, wall time, and CPU time; Linux additionally enforces a child address-space limit.
Partial, empty, encrypted, malformed, oversized, and timed-out results remain explicit.
Derived text carries original content hash, artifact identity, extractor version, text hash, and page numbers.
The new `/api/v1/sources/{artifact_id}/text` endpoint reads captured bytes without exchange ingestion.
Captured document text and provenance enter settlement details, so text/version changes invalidate dependent definitions and approvals.
The browser presents captured text and unresolved source gaps as plain escaped text.

Verified `polymarketexchange.com` through the official end-user legal documentation.
US enrichment captures gateway identity, the official US rulebook, and the official product and notice indexes.
Legal aliases resolve through at most three validated same-host legal-path redirects; other redirects remain rejected.
Current live PostgreSQL capture extracted all 84 pages of the September 30 rulebook and retained the full original bytes.
Rendered the actual first page and inspected it.
Desktop/mobile browser screenshots of real captured US evidence were inspected under `apps/web/test-results/stage3-source-*.png`.

The full SQLite backend suite passed (456 tests); 55 source/review PostgreSQL tests passed; 58 frontend unit tests passed.
Frontend type/lint/generated-contract checks and the production webpack build passed.
The 20 desktop/mobile opportunity browser tests passed, including the added missing-book empty state.
Visual inspection found a catalog contract without monitored quotes showing a generic error; this was replaced with an explanatory empty state.

Stage 3 remains incomplete: gateway-to-product-specification linkage and amendment/clarification applicability are not proven by document index filenames.
No global rulebook or similarly titled PDF is being treated as sufficient instrument-specific settlement evidence.
The source status remains incomplete and live US evaluation remains blocked.
Next action: establish evidence-backed product-document applicability for a real public gateway instrument, then finish joint exceptional-outcome review validation and browser review/auth/access workflows.
Stages 4 through 7, OIDC, reviewed access profiles, actual fee integration, fresh-book publication rechecks, and the full recorded/OIDC acceptance harness remain outstanding.

## Stage 4: counterpart access and joint settlement coverage

Added `market_id` filtering to paginated matches and an exact current-match endpoint.
Reproduced the first-page comparison failure in desktop Playwright before changing frontend loading.
Comparison details fetch their exact pair and referenced contracts independently of catalog pagination.
Each market exposes paginated counterpart browsing, tested beyond 200 pairs on desktop and mobile.
Featured pairs no longer suppress additional pairs solely because a market appeared already.

Reproduced approval of per-venue cancellation coverage without joint-outcome proof through the durable review approval service.
Live OIDC browser reproduction remains unavailable pending identity-provider configuration, so this was the closest existing approval path.
Reviews now require modeled combinations of exceptional and ordinary settlement states or explicit exclusions citing current policy evidence from both venues.
Exclusions must cite the relevant exceptional policy kinds, rather than unrelated policies or title evidence.
Duplicate, unknown, missing, and mismatched joint cases block approval and evaluation.
Legacy payloads remain readable; approvals without required joint cases become ineligible and require renewed review.
Synthetic fixtures explicitly define shared cancellation and do not claim a real venue pair is equivalent.
One-sided cancellation tests demonstrate a valid joint payout calculation eliminating apparent profit.
OpenAPI, review JSON schema, and the TypeScript client were regenerated.

Checks: full SQLite and PostgreSQL suites each passed 460 tests; frontend units passed 58 tests; type/lint/client drift checks passed; four focused desktop/mobile pagination tests passed.
The full browser run passed 48 of 50 tests; two older price-card assertions still expected the pre-existing venue name "Polymarket".
Those assertions were corrected to "Polymarket International", and all 14 market browser tests then passed across desktop/mobile.
The production webpack build passed.

Next action: implement Stage 5 provider-configurable OIDC Authorization Code plus PKCE, durable encrypted browser sessions, evidence-linked review editing, and a versioned reviewed access profile.
An asynchronous request for OIDC issuer/client registration details is pending; live sign-in validation needs that information, but the provider-configurable implementation can proceed independently.
Stage 3 product/amendment applicability still needs evidence-backed review, and Stages 5 through 7 plus the recorded/OIDC acceptance harness remain unfinished.
The pre-existing untracked `backend/arbbot/fees/kalshi.py`, staged research document, and `.specstory` data were preserved.
The isolated PostgreSQL container remains available; inspection API/web/worker processes were stopped.
