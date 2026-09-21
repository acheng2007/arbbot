# Research workstream handoff

## Completed

[X01 #39](https://github.com/acheng2007/arbbot/issues/39) assessed negative-risk market support without enabling it.
The assessment is in [docs/decisions/negative-risk.md](../decisions/negative-risk.md), with recorded group evidence in `backend/tests/fixtures/negative_risk/` and offline checks in `backend/tests/test_negative_risk.py`.
Branch `research/39-negative-risk`.
No support flag, discovery filter, or book rejection changed, and the tests assert those gates still hold.

The decision is continued exclusion of Polymarket negative-risk markets.
Per-question payout is already expressible by the unit binary model, so the blocking problems are mutable outcome sets, unknowable placeholder and residual definitions, and the absence of ingested group evidence for a reviewer to judge.

## Next action

Close the Kalshi group-evidence gap found during this assessment, as a new reviewed issue.

Markets belonging to Kalshi events with `mutually_exclusive` set to true are ingested today.
`mve_filter=exclude` removes multivariate combination events, not mutually exclusive groups, so all 17 recorded Kalshi markets pass the current binary unit-notional filter.
`KalshiAdapter.normalize_market` does not copy `mutually_exclusive` or `collateral_return_type` into `settlement_details`, so a reviewer sees no evidence that an ingested market belongs to a group.

Either ingest those group fields as settlement evidence or exclude mutually exclusive Kalshi events until they can be reviewed as groups.
This is the highest priority follow-up because it affects markets the product already accepts, unlike the Polymarket side which is excluded.

## Notes for the next agent

Required model changes are enumerated in the decision document; items 1 through 5 are matching and review prerequisites, and items 6 and 7 are only needed to trade the Polymarket side or to claim reduced capital.
Do not relax `PolymarketAdapter.supported` to admit negative-risk markets.
Every recorded negative-risk question passes every other structural check, so clearing the flag would admit them silently rather than fail loudly.
Recorded fixtures are immutable evidence with payload digests in `labels.json`; add new recordings rather than editing existing ones.
