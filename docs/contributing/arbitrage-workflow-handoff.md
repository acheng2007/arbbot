# Integrated arbitrage workflow handoff

Status: paused at the user's request on October 12, 2026.
Branch: `backend/completion`.
No PR or push was performed.
The plan is not yet reported complete.

## Saved implementation

Prior commits implemented independent worker scheduling, reviewed execution configuration, conditional US evaluation, catalog-wide browsing, and exact detail views.
This checkpoint adds the isolated recorded-exchange harness using PostgreSQL, production adapters, the persistent worker, FastAPI, Next.js, SSE, and desktop/mobile Playwright.
Four explicitly synthetic pairs cover profitable, unprofitable, blocked, and invalid evaluations.
More than 200 counterpart candidates and unrelated contracts exercise pagination and catalog filtering.
Authentic exchange recordings retain their actual terms and remain unapproved.
Synthetic origins are visibly labeled throughout the browser.
The recording transport has no network fallback or private trading path.

Scheduling fixes separate source enrichment from discovery, restore focused monitoring, prevent split-pair cohorts, persist fee rotation, and coalesce unchanged evaluations.
Source generations and publication locks invalidate every dependent estimate when shared documents change.
Restoring older bytes cannot replay an old approved opportunity.
Transient source failures withdraw estimates and require a fresh calculation after recovery.
Unsupported inventory observations block cached estimates without rewriting original terms.
Fee refresh failures publish explicit unavailable policy revisions and withdraw dependent estimates.
Kalshi policies bind the captured current general fee formula PDF and rounding evidence.
Unverified FCM account fees remain unavailable.
US fees retain the conservative documented cumulative rounded standard cap without simulation fallback.

Additive migration `b023_evaluation_heads` preserves exact financial values using unscaled PostgreSQL NUMERIC and introduces latest-evaluation heads while retaining history.
Book provenance preserves historical IDs for default exchange data.
Source audit counters and empty new price-range defaults do not change historical contract identities.
The initial configuration-import race now uses insert or compare-and-swap semantics.
Generated OpenAPI, TypeScript, and execution configuration schemas were updated.
Operational instructions are in [the workflow guide](../arbitrage-workflow.md).

## Verification at pause

The latest full isolated harness passed and saved artifacts under `/tmp/arbbot-acceptance-verified`.
It demonstrated all four evaluation states, positive publication through SSE, price movement eliminating preliminary profit, fee-provider failure, access/review/fee/source withdrawal, quote expiry, restart/resume, venue outage/recovery, multiple books, and pagination beyond 200 counterparts.
Both connected desktop/mobile Playwright tests passed.
Screenshots from an earlier successful full run were visually inspected.
The latest screenshots still need final visual inspection.
The harness completed and its owned worker, API, and web processes were cleaned up by its finalizer.
The isolated PostgreSQL container and audit schemas remain available.

The latest complete PostgreSQL suite passed 496 tests.
The latest complete SQLite suite passed 495 tests and failed `test_unchanged_quotes_coalesce_evaluation_history` in `backend/tests/test_worker_scheduling.py:134`.
It observed three evaluation records where the test allowed at most two, although exactly one profitable record was present.
An earlier SQLite run passed before the final refinements.
Do not assume the remaining failure is only test timing without reproducing and examining the extra states.
Frontend unit tests passed 58 tests, type checking and lint passed, and the final production webpack build passed.
Generated-client drift checks and backend lint passed.
The earlier 50 fixture-backed browser tests passed before this checkpoint; rerun them after the remaining fix.

Read-only live checks retrieved 100 catalog records from each venue and three books from each venue.
The US sample contained 49 supported and 51 excluded contracts.
Kalshi supplied a continuation cursor and no REST source timestamp.
The real Dodgers pair remained a same-event candidate without equivalence approval or a positive real estimate.
Official fee evidence was captured and hash-verified; fixtures retain original official documents.
No real installation access, real product equivalence, or actual trade was approved.
OIDC and browser review editing remain deferred as requested.

## Resume

Next action: reproduce and resolve the SQLite scheduling-history failure before changing any additional functionality.
Then rerun the affected checks, inspect the latest desktop/mobile artifacts, rerun the 50 fixture browser tests, and review remaining acceptance coverage before declaring the full plan complete.
Connected loading, error, and stale browser states need final coverage review; the connected acceptance currently covers empty results and SSE recovery while existing fixture tests cover the broader state set.

The user's pre-existing staged research document, `.specstory/`, and untracked `backend/arbbot/fees/kalshi.py` prototype are excluded from this checkpoint.
Do not adopt or commit those files incidentally.

## October 12 inspection demo

Implementation remains paused.
At the user's request, a fresh recorded PostgreSQL / worker / API / Next.js demo is running at `http://127.0.0.1:3000/opportunities`.
The backend is `http://127.0.0.1:49278`; the runner tool session is `88418`.
Runtime metadata, process IDs, recording, control file, and logs are under `/tmp/arbbot-show-demo/`.
The temporary launcher is `/tmp/arbbot-show-demo.py`.
The dashboard returned HTTP 200 and the opportunity API returned a synthetic positive estimate.
Synthetic results are labeled and are not real profitable market evidence.
Review and access seed evidence expires after one hour; estimates may disappear when that evidence expires.
The services are left running for inspection.
Automatic approval review blocked selecting Firefox because it would expose an unrelated private page; no browser navigation was completed.
Next action: open the local demo link to inspect it; implementation still resumes with the SQLite scheduling-history failure.
