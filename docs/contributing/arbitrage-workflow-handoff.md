# Integrated arbitrage workflow handoff

Status: the requested Kalshi / Polymarket US workflow is implemented and its acceptance checks passed.
Branch: `backend/completion`.
No PR or push was performed.
OIDC, browser review editing, automatic trading, private account integrations, and additional exchanges remain outside this completed scope.

## Delivered workflow

The persistent worker independently supervises broad discovery, source enrichment, matching, fee refresh, complete-pair monitoring, and evaluation.
Discovery scope and progress, monitoring rotation, books, and per-market health persist across restart.
Matching distinguishes title suggestions, established same events, verified equivalence, and rejection without filling unknown settlement facts.
Reviewed applicability, exact captured source generations, access profiles, fee policies, drafts, and decisions use immutable revisions and optimistic concurrency.
The local operator CLI supports evidence-aware validation without importing, authenticated-repository imports, and bounded official-host source capture.
Unknown, restricted, expired, changed, or unsupported inputs stay blocked.

The pure Decimal engine calculates supported US native long and short exposures, whole-contract sizing, depth costs, fee bounds, slippage, capital, and every reviewed settlement outcome.
Short proceeds, gross collateral, net buying power, and settlement payoff remain separate.
Evaluations expose profitable, unprofitable, blocked, and invalid results, including signed executable results below the profit threshold.
Positive preliminary results refetch both books and pass transaction-level approval, configuration, source, health, and quote guards.
Changes and expiry withdraw estimates, and recovery calculates new estimates without replaying old approvals or offers.
Kalshi policy refresh binds the current general fee formula and rounding documentation, plus current and scheduled overrides.
Unverified non-direct account charges remain unavailable.
US policies use the conservative documented cumulative rounded standard taker cap without rebates, discounts, or simulation cost substitution.

Additive migrations `b022_execution_configuration` and `b023_evaluation_heads` preserve historical identities and payloads, exact PostgreSQL monetary values, immutable evaluation history, and latest-evaluation lookup.
The browser supports catalog-wide filters, paginated summaries, comparisons and counterparts beyond 200 entries, exact details, native exposure breakdowns, source evidence, and input freshness.
US fee presentation identifies the policies used in the calculation independently of settlement review.
Exact opportunity details expose eligible/invalidated status and current invalidation reasons without modifying the historical calculation payload.
SSE refreshes coalesce pending reads instead of repeatedly cancelling them.
Opportunity cards retain their DOM identity as quotes refresh, preserving navigation during updates.
Long reviewer identifiers wrap on mobile, and settlement tables fit narrow screens.
Recorded and synthetic origins are visibly labeled and never presented as real profitable evidence.

## Final verification

SQLite: 497 tests passed.
PostgreSQL: 497 tests passed, including additive migration preservation and exact NUMERIC round trips.
The scheduling-history failure was reproduced through the worker and ASGI API before changing the test.
Its three startup records were distinct legitimate states: two books missing, one book missing, then profitable.
The corrected assertions permit those transitions while rejecting duplicate states and duplicate positive evaluations.
Backend lint and formatting passed for all 135 Python files.
All four published schemas match fresh exports, and generated TypeScript contract checks passed.
The execution schema drift check is now included in backend CI.
Frontend units: 58 tests passed.
Frontend type checking, lint, and production webpack build passed.
Fixture-backed desktop/mobile Playwright: 50 tests passed.
Connected desktop/mobile Playwright: four tests passed.

The final full PostgreSQL / production-adapter / persistent-worker / FastAPI / Next.js acceptance run passed under `/tmp/arbbot-acceptance-final-contract`.
It demonstrated four independently reviewed synthetic pairs, all four evaluation states, multiple books, pair rotation, restart/resume, positive publication through SSE, publication-time price movement eliminating preliminary profit, fee-provider outage, access/review/fee/source withdrawal, quote expiry, venue outage, recovery, exact lookup, and pagination beyond 200 counterparts.
Connected UI checks include loading, manual retry with the stream unavailable, empty results, actual stale recorded quotes, and recovery.
Final desktop/mobile calculation, review, error, stale, and counterpart screenshots were visually inspected.
The mobile calculation was separately measured at 390 pixels of content width on a 390-pixel viewport after correcting the reproduced 516-pixel overflow.
Recorded source bytes and authentic contracts were not rewritten or approved to satisfy acceptance.
See [the acceptance record](arbitrage-acceptance-2026-10-12.json) and [the workflow guide](../arbitrage-workflow.md).

## Live observations and operational limits

The final public read-only smoke check fetched 100 catalog records from each venue and three books per venue.
US observations contained 49 supported and 51 excluded instruments in the sports sample.
Kalshi supplied a continuation cursor and no REST source timestamp.
The real Dodgers pair `08b6abf41faeeeb60d3e77206a9b33fcedc03fb5761b0ce2625610dfbb8bd09d` remained an unapproved same-event candidate.
No real installation access, real equivalence approval, or positive real opportunity was asserted.
Live activation requires an operator's supported access evidence and evidence-backed applicability and settlement review for the selected real products.
Missing evidence remains visible and blocked.
Balances, inventory, non-atomic fills, and unverified account charges remain explicit limitations.

The isolated acceptance services and temporary inspection services have been stopped.
The local PostgreSQL container and audit schemas remain available.
Worker leases are shared across schemas in one database; stop other workers or use a separate database URL before running acceptance.
Failed acceptance runs preserve diagnostics and runtime metadata without account credentials.
The user's pre-existing staged research document, `.specstory/`, and untracked `backend/arbbot/fees/kalshi.py` prototype remain excluded.

Next action: inspect the completed acceptance artifacts, then prepare a reviewed evidence package for the first real same-event candidate using the operator CLI.
There are no remaining acceptance failures for this scope.
