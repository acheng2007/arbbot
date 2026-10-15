# Candidate visibility and automatic verification

Status: accepted product direction, October 15, 2026.
This decision governs future development of candidate discovery, comparisons, qualification, and result presentation.
It supersedes using Jev probability/confidence cutoffs as admission requirements for displaying same-event suggestions.
This is a documentation decision; the running code has not yet been migrated to this policy.

## Decision

Retain and expose every valid, fresh Jev `same_event` suggestion for an identified counterpart pair, even when model probability or confidence is below the current 0.80 cutoffs.
Use model scores to explain and rank unverified suggestions within bounded, fairly scheduled work; do not use a minimum score to hide them from candidate browsing.
A suggestion is not settlement equivalence, and displaying it does not authorize financial publication.
Deterministic counterpart discovery remains operational without Jev or a configured provider key.
No per-pair human review is required.

## User-facing meanings

| Label | Meaning | Financial implication |
| --- | --- | --- |
| Unverified match | A current possible counterpart whose automatic settlement checks are pending, incomplete, or unavailable | Does not establish compatible payouts; eligible potential price gaps may be shown separately |
| Verified match | Current automatic evidence, applicability, definition, and settlement-payout checks passed | Does not establish profitable prices or an individual user's ability to execute |
| Mismatch | Automatic checks found an explicit event or settlement contradiction | Cannot support a qualified arbitrage estimate; retain the suggestion and conflicting evidence for inspection |
| Arbitrage estimate | A verified relationship also passes current depth, public fee, rounding, capital, slippage, freshness, quote-recheck, and publication checks with positive modeled worst-case net result | Conditional estimate with fill, account, and execution assumptions; never guaranteed profit |

These are product meanings, not a claim that the current API already exposes a new status enum.
Keep pending, incomplete, unavailable, stale, disabled, and unconfigured reasons inspectable rather than collapsing them into unexplained failure.
Preserve explicit historical human-review labels and their provenance; do not invent a reviewer for automatic verification.

## Verification and current validity

Automatic Python qualification remains the authority for settlement compatibility.
A Jev event or clause answer, regardless of its score, cannot manufacture missing evidence or grant verified status.
Unknown clauses, missing applicability, unsupported interpretation, and absent payout coverage leave a suggestion unverified.
Explicit contradictions produce Mismatch rather than an unverified assertion of compatibility.
Do not hide a conflicting suggestion's evidence or present it as a current arbitrage estimate.
Existing operator vetoes remain effective and are not overridden by model advice.
Negative or insufficient-evidence Jev findings do not remove independently supported deterministic proposals.

Verification is independent of current profitability and public fee/quote availability.
A verified relationship can have no opportunity, while missing or stale financial inputs withdraw estimates without fabricating a settlement conflict.
Changed settlement terms, document generations, policy/provider versions, or assessment expiry can invalidate verification and expose its current reason.
Changed inputs invalidate model advice independently.
Stale, disabled, or malformed advice cannot create a current AI-only suggestion; preserve historical inspection and retain pairs independently supported by current deterministic evidence.
No browser or API read may silently promote a historical result back to current status.

## Retrieval, ranking, and presentation

This policy admits suggestions that Jev actually returns for supplied pairs; it does not require unbounded all-pairs model calls or imply exhaustive exchange coverage.
Retain deduplication, request pacing, bounded queues, durable cursors, and explicit catalog/retrieval/monitoring limits.
A ranking decision or monitoring budget may affect order and quote refresh frequency, but must not become an undisclosed confidence-based candidate admission cutoff.
Keep settlement-supported and established-event monitoring priorities, with fair rotation and visible quote availability for unverified pairs.

Show Unverified and Verified comparisons distinctly, with Mismatch and historical states inspectable through explicit status controls/details.
Show model confidence and probability as model scores, not statistical confidence intervals or measured accuracy.
Display source evidence, automatic check reasons, data origin, and timestamps alongside the basis for each status.
Do not require a human approval screen before a suggestion becomes visible.
Potential ordinary-outcome price gaps and qualified arbitrage estimates remain separate feeds and labels.
Lack of a positive spread must not hide a verified contract comparison.
Apply current validity, status filtering, and ranking before pagination; refresh through the existing snapshot-driven query path.

## Current implementation and required follow-up

The current classifier, matcher, API eligibility checks, and monitoring still rely on the threshold-derived `supports_candidate` behavior.
The default paired browser also relies on established-event filtering and does not yet implement this complete visibility policy.
Changing environment thresholds alone is not implementation of this decision.
The existing 30-pair live benchmark records the old admission policy; keep those observations immutable rather than relabeling them as a new-policy result.
All 30 authentic pairs remain incomplete for automatic settlement qualification.

The next implementation must carry the new candidate eligibility consistently through storage/current projections, matching, monitoring, filtered APIs, browser queries, labels, and evidence details.
Preserve historical review/read compatibility and regenerate OpenAPI/TypeScript contracts if public shapes change.
Do not overload a legacy human approval or profit classification with a new meaning without an explicit compatible mapping.

Acceptance must demonstrate:

- A low-score, valid current `same_event` finding is visible as Unverified through paginated APIs and desktop/mobile browsing.
- Incomplete evidence and provider failures have inspectable reasons and cannot grant verification.
- Complete supported automatic evidence grants Verified without human records, even if current prices are unprofitable or financial inputs are unavailable.
- Explicit contradictory periods or settlement clauses show Mismatch and cannot enter qualified estimates.
- Source changes, advice expiry/disablement, late responses, operator vetoes, and quote/fee outages preserve their independent validity boundaries.
- Positive financial publication still requires current settlement verification and every existing financial and freshness gate.
- Ranking, bounded monitoring, and snapshot refresh do not silently discard low-score suggestions or reset pagination/navigation.

## Next action

Implement this decision across the existing matching/API/browser workflow on a focused branch from main, with a low-score live-response replay and connected desktop/mobile acceptance before describing the policy as delivered.
