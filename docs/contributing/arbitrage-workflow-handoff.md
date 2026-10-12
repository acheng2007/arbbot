# Integrated arbitrage workflow handoff

Branch: `backend/completion`.
No PR was opened or push performed.

## Completed implementation

The persistent live worker now supervises discovery, coalesced source enrichment, matching, quote polling, fee refresh, and evaluation independently.
Matching runs off the event loop and wakes when catalog or captured source content changes.
Broad discovery is the live default; watchlists prioritize rather than restrict broad queries.
Pair monitoring uses durable rotation offsets and allocates both legs within each venue budget.
Fresh per-market health and immutable books survive cohort rotation.
Fresh persisted catalog state is restored before network refresh after restart.
Matching generations and pair-specific evaluation publication are separate operations.

Additive migration `b022_execution_configuration` stores immutable access, applicability, and fee revisions with current heads.
Authenticated configuration writes and local operator imports share repository evidence validation, operator attribution, optimistic concurrency, and immediate withdrawal.
Reviewed applicability retains exact artifact hashes and quotations, exposes selected document text for definition evidence, and discharges only the two explicitly reviewed applicability gaps.
Other missing source facts remain unresolved.
US review decisions bind applicability revision identities; changes require another review.
Public venue metadata now identifies US evaluation as conditionally supported, with the required evidence gates disclosed.
The operator module supports schema validation, imports, and bounded official-host document capture.

US calculation uses explicit access, applicability, settlement, quote, and fee gates instead of the blanket discovery-only rejection.
Native price grids and whole-contract orders are enforced.
US NO legs expose the native short action and price, proceeds, gross collateral, and net buying power separately.
Positive estimates reserve gross short collateral conservatively.
Evaluations distinguish profitable, unprofitable, blocked, and invalid inputs and retain signed calculations below the profit threshold.
Live positive results refetch both books concurrently before calculation and recheck exact snapshots, per-market health, approval, access, applicability, and fee revisions in the publication transaction.
Public reads also revalidate configuration and source eligibility.

Fee refresh retrieves current series policies, complete paginated event overrides, and scheduled series changes outside calculation.
Unknown policies and execution granularity remain unavailable.
US standard taker fees use the documented cumulative half-even rounded cap.
The implementation conservatively uses the higher documented standard coefficient of 0.10 for all supported US standard instruments, avoiding an unverified Table Tennis classification or discount.
The Kalshi partition-independent bound includes model fees plus one microdollar and one account precision unit per possible minimum execution.
This deliberately coarse bound does not assume accumulator rebates exhaust the final residual.
Non-direct account estimates can consequently be excessively conservative.
The pre-existing untracked `backend/arbbot/fees/kalshi.py` prototype was inspected but is not adopted or committed.

The API exposes filtered paginated lightweight market summaries, exact opportunity state, sanitized installation-access status, and latest evaluations per pair with explicit historical access.
Browser search, status, category, and venue filtering run before pagination.
Comparison lists paginate and resolve referenced contracts by ID.
Cards look up counterparts independently of the first comparison page.
Opportunity details use exact IDs; blocked rows use exact pair and contract reads.
US shorts display native actions and collateral figures.
Snapshot events refresh affected catalog, comparison, evaluation, opportunity, quote, and status queries without claiming freshness from connectivity.
OpenAPI and the generated TypeScript client include the new execution contracts; `docs/execution.schema.json` describes operator configuration input.
The schema generator now supports discriminated `oneOf` unions.
The settlement payout table now labels gross payout correctly rather than calling it net result.

## Validation and limitations

The complete SQLite suite passed 480 tests after the integrated implementation.
Focused checks cover subsequent policy-input, venue-registration, and repository-pagination refinements.
A publication recheck test moves both synthetic books before publication and proves preliminary profit disappears.
Thirteen new synthetic financial/configuration tests passed, including fragmented executions, cumulative US rounding, short collateral, signed negative results, stale inputs, revision conflicts, and captured quotation validation.
The new catalog-wide summary test queries a target beyond 200 stored contracts and verifies detail payloads stay out of list rows.
Frontend unit tests passed 58 tests, TypeScript and lint passed, and generated-contract checks passed.
The production webpack build passed.
All 50 fixture-backed desktop/mobile Playwright tests passed after comparison pagination and access-summary refinements.
Desktop/mobile market screenshots were visually inspected without document overflow.
These browser fixtures are explicitly labeled; they are not evidence that the persistent PostgreSQL-backed US workflow has passed.

Read-only live checks fetched 100 US catalog records, supported 51, excluded 49, and fetched a 13-level book on each side of the observed US contract.
Kalshi returned a continuing catalog page and an 88-level YES / 64-level NO book for the inspected contract.
The observed US sample was sports, and Kalshi REST still supplied no source timestamp.
The final smoke check also retrieved the real Dodgers counterpart and proposed match `08b6abf41faeeeb60d3e77206a9b33fcedc03fb5761b0ce2625610dfbb8bd09d` as a same-event candidate.
It remains unapproved and requires settlement and cost review.
That later check observed 14 YES / 13 NO US levels and 81 YES / 54 NO Kalshi levels; these are observations rather than fixed expected counts.
No positive real opportunity was asserted and no actual installation access or product equivalence was approved.
Official US fees were verified at https://docs.polymarket.us/fees, including the October 7 effective date and cumulative commission cap.
Official Kalshi fee rounding, fixed-point execution granularity, series changes, and paginated event changes were read during implementation.

Docker Desktop reports that it is manually paused.
The computer-use attempt to inspect Docker timed out, and no local PostgreSQL executable was found.
Fresh PostgreSQL migration preservation and suite results are therefore unavailable.
No PostgreSQL result is claimed from SQLite runs.

## Incomplete acceptance and next action

The requested isolated recorded-exchange PostgreSQL / persistent-worker / FastAPI / Next.js acceptance harness has not been built or passed.
Three-pair publication through SSE, worker restart/resume under that harness, publication-time price movement, configuration withdrawal, quote expiry, outage and recovery still require integrated acceptance coverage.
Existing tests cover several components independently, which does not fulfill that requirement.
Fee retrieval and reviewed document applicability also need recorded adapter-level acceptance using the newly captured current policies.
Operator validation currently validates schemas without importing; evidence and concurrency validation occurs during import.
No OIDC or browser review editing was added, as requested.

Next action: resume Docker Desktop and implement the isolated recorded-exchange acceptance harness against migration `b022_execution_configuration`, keeping synthetic profitability visibly separate from authentic settlement recordings.
Run PostgreSQL suites and migration preservation, then complete the outstanding integrated scenarios before describing this workflow as finished.
