# US-accessible venue expansion

## Objective and boundaries

Compare supported prediction-market contracts across venues available to US traders and identify mispricing between equivalent outcomes.
Discover broadly across market categories, retain absent counterparts, and report coverage instead of hiding unsupported markets.
A displayed price difference is a candidate discrepancy; an actionable estimate additionally requires matching settlement rules, eligible access, current executable depth, complete costs, and human approval.
Keep two-leg strategies and manual trading decisions.
Automatic orders, custody, transfers, baskets, negative-risk instruments, and portfolio margin optimization remain outside this milestone.

## Candidate integrations

Official documentation reviewed October 1, 2026 supports the following assessment order.
These are integration candidates, not a claim that every account or state can trade every listed product.

| Venue | Role and evidence | Required validation |
| --- | --- | --- |
| Kalshi | Existing baseline integration | Current account/product eligibility, complete rule evidence, automated fees |
| Polymarket US | First new adapter; its [data guide](https://docs.polymarket.us/data-guide/overview) documents reference data and order-book access | Verify retail versus institutional access, API behavior, fees, restrictions, and overlapping contracts |
| Crypto.com Predictions / CDNA | Second candidate; [official help](https://help.crypto.com/en/articles/11373970-prediction-trading) describes US availability and CDNA onboarding; [market-data docs](https://data-api.crypto.com/docs) are published | Verify prediction-specific endpoints, payout units, rule retrieval, fee rounding, and product/state availability |
| ForecastEx via IBKR | Third candidate, especially for economic contracts; [IBKR API documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/event-contracts/) describes event discovery | Verify authenticated market-data access, subscriptions, trading permissions, settlement terms, and fee/position semantics |
| CME via IBKR | Separate candidate exchange, sharing broker access where supported | Verify actual offered instruments, payouts, permissions, API depth and equivalent counterparts independently of ForecastEx |

[IBKR's product page](https://www.interactivebrokers.com/predictionmarkets/en/home.php) lists access to Kalshi, CME, and ForecastEx for eligible clients.
A broker route to Kalshi is not another independent Kalshi order book.
Record exchange identity separately from broker or distribution channel so shared liquidity is not double-counted.
Polymarket US must have its own ID, adapter, fee policy, rules, and fixtures; never relabel existing International records.
Opinion and Limitless are deferred and excluded from the US milestone.

## Delivery sequence

The [implementation roadmap](implementation-roadmap.md) gives the current implementation order.
Finish the existing Kalshi/Polymarket US discovery and review-to-estimate path before implementing another venue.
The stages below describe acceptance boundaries; initial work is already present at the scopes listed in Current status.

### 1. Establish access and actual coverage

Record country, state, account permissions, and product restrictions as separate evidence-backed eligibility inputs.
Unknown eligibility permits research comparison but blocks actionable estimates.
Public market-data access alone does not establish trading eligibility.
Capture timestamped immutable catalogs, settlement rules, order books, fee schedules, restrictions, and request provenance for each candidate.
Start with Polymarket US and compare its real catalog against Kalshi before promising an overlap family.
Retain CPI and Fed discovery, while inventorying other categories such as sports, weather, politics, and crypto where documented access permits.
Add each category's semantics explicitly, including tie, cancellation, postponement, measurement time, and source rules.
Record missing data, unavailable access, rejected instruments, and absent counterparts as results.

Exit: a reviewed capability matrix and recorded fixtures identify the first feasible independent exchange pair.

### 2. Generalize the integrated product

Introduce a venue registry with stable IDs, adapter factories, enabled states, capabilities, and eligibility evidence.
Use per-venue discovery settings within shared event families and explicit extraction dispatch.
Add a venue API and regenerate OpenAPI and TypeScript together.
Preserve historical IDs, artifacts, review hashes, and evaluation records with additive migrations.
Exclude International quotes from US actionable estimates while retaining historical research records.
Do not silently infer eligibility for existing approvals.

Exit: registered venues flow through ingestion, storage, matching, API reads, and responsive venue panels.

### 3. Compare all supported counterparts

Paginate complete catalog traversal and event comparisons; remove first-200-match and one-pair-per-market presentation limits.
Use event grouping for navigation and candidate discovery only.
Evaluate every supported venue pair independently; similarity and shared event membership do not establish equivalent settlement.
Expose raw discrepancies alongside explicit blocked reasons and independently reviewed comparisons.
Normalize payout units, settlement assets, tick sizes, minimum orders, executable depth, and venue-specific costs.
Complete source evidence, versioned fee providers, exceptional-settlement checks, authenticated review editing, and immediate quote rechecks before actionable estimates.
Bound polling and retries and isolate failures by venue and market.

Exit: each accepted candidate has a reproducible evidence-to-review-to-estimate path, with all unsupported assumptions visible.

### 4. Validate usefulness and roll out

Test every implemented venue pairing, category conflicts, absent counterparts, fee rounding, depth sizing, stale books, eligibility restrictions, duplicate broker routes, and partial outages.
Verify historical migrations and synchronized generated contracts.
Run desktop/mobile browser workflows with review conflicts and approval invalidation.
Enable each venue for discovery first and evaluation only after its gates pass.
Run seven actual days of forward paper observations at $100, $500, and $1,000 budgets with 5, 15, and 30 second quote rechecks.
Record rejected candidates, coverage gaps, net estimates, and candidate lifetime.
A positive opportunity is not a release requirement.
Follow with streaming coverage, dashboards, staging, and backup/recovery validation.

## Current status

Reconciled October 11, 2026 on `backend/completion`.
The earlier Opinion/Limitless implementation was rolled back and remains deferred.
Local uncommitted work now includes Polymarket US catalog/book/fee/restriction recordings, a separate REST adapter, World Series candidate extraction, a stable venue registry/API, configured catalog filtering, and venue-aware browser panels.
The recorded Dodgers pair is a rule-backed same-event candidate with incomplete settlement evidence, not a reviewed equivalent pair.
Polymarket US evaluation is explicitly blocked on rules, fees, and access verification.
Enabled-venue filtering does not establish account/product eligibility.
The unfinished local Kalshi fee provider is not connected to automatic evaluation.

Full SQLite backend and frontend unit/type/lint/contract checks passed on October 11 at the counts recorded in the [integrated status handoff](contributing/project-status-handoff.md).
Docker is unavailable, so fresh running-stack PostgreSQL, migration, and desktop/mobile smoke validation remains required.
No complete US eligibility model, automatic US fee integration, authenticated browser review workflow, immediate quote-recheck path, or seven-day study has been delivered.
Crypto.com and ForecastEx/CME assessments remain future work; candidate descriptions above retain their October 1 evidence date.

Next action: restore Docker and finish integrated validation and capability documentation for the existing US discovery work.
Then complete source/exception evidence, eligibility gates, fees, authenticated reviews, and freshly rechecked conditional estimates for a supported pair before adding another venue.
If settlement incompatibility prevents approval, preserve the conflict and assess another pair.
See the [US expansion handoff](contributing/us-expansion-handoff.md) for concrete acceptance checks.
