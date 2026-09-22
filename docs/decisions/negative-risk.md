# Negative-risk market support

Status: continued exclusion, with a narrow conditional path described below.
Decision date: 2026-09-20.
Scope: whether Polymarket negative-risk questions and Kalshi mutually exclusive market groups can be represented by the existing unit binary model.
This document does not change adapter support flags, and no implementation is authorized by it.

## Evidence

Recorded group metadata is in `backend/tests/fixtures/negative_risk/recorded.json` with source URLs and UTC capture timestamps.
Independently read structural facts and payload digests are in `labels.json`, and payoff examples are in `payoffs.json`.
`backend/tests/test_negative_risk.py` replays the evidence offline and checks the payoff arithmetic.
No order books, credentials, or account data are recorded, and no price is presented as current.

Four live groups were captured on 2026-09-20.

| Group | Venue | Mechanism | Questions | Residual outcome |
| --- | --- | --- | --- | --- |
| `606422` Fed Decision in October? | Polymarket | Standard negative risk | 5 | Rounding rule to the nearest 25 basis points |
| `KXFEDDECISION-26OCT` Fed decision in Oct 2026? | Kalshi | Mutually exclusive event | 5 | None |
| `81557` Prime Minister of Israel after the next election? | Polymarket | Augmented negative risk | 28 | Explicit `Other` bucket |
| `KXNEXTISRAELPM-45JAN01` Who will succeed Netanyahu as Prime Minister of Israel? | Kalshi | Mutually exclusive event | 12 | None |

Venue documentation used for mechanics:
[Polymarket negative risk](https://docs.polymarket.com/advanced/neg-risk),
[NegRiskAdapter contract reference](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/NegRiskAdapter.md),
[Kalshi get-event](https://docs.kalshi.com/api-reference/events/get-event),
[Kalshi get-markets](https://docs.kalshi.com/api-reference/market/get-markets),
[Kalshi market settlement](https://docs.kalshi.com/getting_started/market_settlement),
and [Kalshi collateral return](https://help.kalshi.com/en/articles/13823816-collateral-return).

## What the product does today

Polymarket discovery rejects any market whose payload sets `negRisk`, and book normalization raises on a CLOB response carrying `neg_risk`.
Kalshi discovery requests `mve_filter=exclude` and additionally skips markets that are not `binary` or whose `notional_value_dollars` is not exactly 1.

Two findings qualify that summary.

First, every recorded negative-risk question already has unit binary shape.
Each one exposes `outcomes` of `["Yes", "No"]`, exactly two CLOB token ids, an end date, and an enabled order book.
Clearing only the `negRisk` flag makes each of the 33 recorded questions pass `PolymarketAdapter.supported`.
The exclusion is therefore a deliberate group-level policy rather than a shape mismatch, which matters because it means relaxing the flag would silently admit these markets rather than fail loudly.

Second, Kalshi mutually exclusive groups are not excluded today.
`mve_filter` filters multivariate events, which are combination markets, and it does not filter events whose `mutually_exclusive` field is true.
All 17 recorded Kalshi markets pass the current binary unit-notional filter, so markets from both recorded Kalshi groups are already eligible for ingestion, matching, and evaluation.
`KalshiAdapter.normalize_market` copies `event_ticker` into `settlement_details` but not `mutually_exclusive`, `collateral_return_type`, or the sibling market set, so a reviewer inspecting an ingested Kalshi market sees no evidence that it belongs to a mutually exclusive group.

## Conversion and collateral differences

Polymarket relates the questions in a group through an on-chain conversion.
Holding the same `amount` of the NO token for `m` of the `n` questions, `convertPositions` burns those NO tokens and returns `amount` of each of the `n - m` complementary YES tokens plus `amount * (m - 1)` collateral.
An optional per-market fee rate reduces the YES output to `amount - amount * feeBips / 10000`.
Negative-risk questions trade through the Neg Risk Adapter and Neg Risk CTF Exchange rather than the standard CTF exchange, so token identities, approvals, and the book payload differ from the markets the product supports today.

Kalshi has no conversion operation.
It instead offers collateral return, which nets the capital requirement for positions on the non-mutually-exclusive sides of a mutually exclusive group, normally NO positions.
Both recorded Kalshi events report `collateral_return_type` of `MECNET`.
Collateral return is an account setting that is disabled by default for new users, so its effect cannot be assumed from market metadata alone.

The consequence for capital is asymmetric.
Both mechanisms can reduce the capital required to hold a basket relative to the per-leg sum, and the engine currently reserves each leg at its limit price with no netting.
That makes the reported capital requirement conservative rather than wrong, which is the safe direction, but it also means a netted figure must never be presented without verifying that the specific account is eligible.

## Payout differences

A single question on either venue pays one unit of the settlement asset to the correct side, so per-question payout is already expressible.
The differences are at group level.

Mutual exclusivity bounds the number of YES resolutions to at most one, and both venues state this as an upper bound rather than an exact count.
The Kalshi secondary rules for the recorded Fed event say that only one bucket at maximum can resolve Yes.
The Polymarket adapter reference states that it is not possible for more than one question to resolve true, and separately describes the case where all questions resolve false.
Neither venue guarantees that exactly one question resolves YES, so an all-NO settlement is possible in both.

Conversion is only value preserving while at most one question can pay.
The arithmetic is verified in `payoffs.json` and reproduced in the tests.

| State | Value of `m` held NO tokens | Value after conversion |
| --- | --- | --- |
| The resolving question is inside the converted set | `m - 1` | `m - 1` |
| The resolving question is outside the converted set | `m` | `m` less any conversion fee |
| No question resolves YES | `m` | `m - 1` |

The all-NO state loses exactly one unit of `amount` relative to holding the NO tokens, and a nonzero fee rate reduces the middle row further.
A model that treated conversion as a free rewrite of one basket into another would overstate the payoff in precisely the state that makes a mutually exclusive group unusual.

## Exceptional settlement differences

Augmented negative risk makes the outcome set mutable after trading begins.
The recorded Israel group is augmented and contains nineteen named candidates, eight unnamed placeholders named `Person H` through `Person O`, and an explicit `Other` bucket.
Polymarket clarifies a placeholder into a real candidate through its bulletin board, and the definition of `Other` narrows each time that happens.
Polymarket instructs traders to use only named outcomes, states that its interface does not display unnamed outcomes, and warns against trading `Other` directly because its definition changes.
Placeholder questions are nonetheless returned by the public API and pass every structural check the product applies.

This breaks the product's approval invalidation guarantee.
`Market.terms_hash` covers one market's title, rules, close time, asset, tokens, and `settlement_details`.
The recorded `Other` question asks whether "another person" will be the next Prime Minister, and that text does not change when a placeholder is clarified.
The test `test_clarifying_a_placeholder_does_not_invalidate_sibling_approvals` shows the group composition changing while the `Other` market's `terms_hash` stays identical, so a prior approval of that question would survive a change in its meaning.

The venues also differ on residual coverage.
The Polymarket Israel group is closed by an explicit `Other` bucket, while the Kalshi event names twelve successors and has no residual market, so an unnamed successor settles all twelve to NO.
The named sets are not the same: Kalshi lists Yoav Gallant and Bezalel Smotrich, who are absent from the Polymarket named set, and Polymarket lists candidates absent from Kalshi.

## Counterexamples

Each pair below is title-similar and structurally eligible, and each fails on evidence.
In every case a review restricted to the two ordinary outcomes the `Review` model requires sees a guaranteed payout of one unit in both trade directions, while an evidenced third state pays nothing in one direction.

A cut of 12.5 basis points separates the Fed brackets.
Each Kalshi bucket names an exact move, and the five recorded buckets are a cut greater than 25 basis points, a cut of 25, a hike of 0, a hike of 25, and a hike greater than 25, so a 12.5 basis point cut matches none of them and all five settle to NO.
Polymarket rounds any change up to the nearest 25 and gives a 12.5 basis point move as its own example, so its 25 basis point decrease bracket resolves YES.
Buying Kalshi YES against Polymarket NO pays nothing in that state.
The authoritative Kalshi text is also weaker than its label here: `rules_primary` for the `Cut >25bps` bucket reads "does a Cut of   25bps" and omits the boundary that appears in the subtitle and in the sibling hike bucket, so the rule text alone cannot establish the bracket edge.

The Israel horizons differ.
The Kalshi event resolves YES whenever the named person succeeds Netanyahu at any time before 1 January 2045, while the Polymarket question is limited to the Prime Minister sworn in after the 2026 parliamentary election and ends 31 December 2026.
If Netanyahu is returned to office after the 2026 election and Israel Katz succeeds him in 2031, the Polymarket question has already resolved NO and the Kalshi market later resolves YES.
Buying Kalshi NO against Polymarket YES pays nothing in that state.

The residual bucket matches nothing.
Polymarket `Other` resolves YES for any unnamed winner, so it cannot be equivalent to a single Kalshi candidate market.
Bezalel Smotrich taking office resolves both the Kalshi Smotrich market and Polymarket `Other` to YES, but Yoav Gallant taking office resolves Polymarket `Other` to YES and the Kalshi Smotrich market to NO.
Buying Kalshi YES against Polymarket NO pays nothing in that state.

A fourth counterexample needs no cross-venue pair.
Converting NO tokens inside one Polymarket group is not payoff neutral when every question resolves NO, as shown in the payout table above.

## Required model changes

Supporting these markets would require all of the following, and none of them exist today.

1. Ingest group identity and structure as evidence: `negRiskMarketID`, `negRiskAugmented`, `negRiskOther`, and the question set for Polymarket, and `mutually_exclusive`, `collateral_return_type`, and the sibling market set for Kalshi. None of these reach `settlement_details` now.
2. Bind approval to group composition, so that adding a question, clarifying a placeholder, or narrowing a residual bucket invalidates prior approvals for every question in the group. A per-market `terms_hash` cannot express this because the changed field belongs to a sibling.
3. Record residual coverage explicitly, distinguishing an explicit residual bucket, a rounding rule, and no residual coverage, and treat a mismatch between two groups as a rejected match rather than an unresolved difference.
4. Require reviewers to enumerate group states rather than only the two ordinary outcomes. The current `Review` validator accepts a scenario set that omits an evidenced divergence, which `test_review_accepts_scenarios_that_omit_an_evidenced_divergence` demonstrates.
5. Exclude unnamed placeholder questions and residual buckets from matching outright, since their definitions are not knowable at trade time.
6. Support the Neg Risk CTF Exchange book surface before any Polymarket negative-risk quote is used, replacing the current rejection in `normalize_book` with real handling of its token identities, tick size, minimum size, and fee type.
7. Model conversion and collateral return conservatively if they are ever used for capital, including the all-NO deficit and the conversion fee, and never present a netted capital requirement without verifying account eligibility.

Items 1 through 5 are matching and review concerns and are prerequisites for any evaluation.
Items 6 and 7 are only needed to trade the Polymarket side or to claim reduced capital.

## Recommendation

Continue to exclude Polymarket negative-risk markets.
The blocking problems are not payout representation, which the unit binary model already handles per question, but mutable outcome sets, unknowable placeholder and residual definitions, and the absence of any ingested group evidence for a reviewer to judge.

Treat the current Kalshi behavior as a gap to close rather than as support.
Markets from mutually exclusive Kalshi events are ingested today with no record that they belong to a group, which is the same missing evidence that makes the Polymarket side unsafe.
Closing that gap means either ingesting the group fields named in change 1 or excluding mutually exclusive Kalshi events until they can be reviewed as groups.
This is the highest priority follow-up because it affects markets the product already accepts.

A narrow future path exists and is deliberately not taken here.
A non-augmented group with a fixed, fully named outcome set, matched question by question against a venue whose brackets align exactly, is representable once changes 1 through 4 are in place.
The recorded Fed pair is the closest case, and it still fails on bracket rounding, which is a resolution-rule difference rather than a structural one.

Any implementation requires a separate reviewed issue.
This assessment does not relax `PolymarketAdapter.supported`, the Kalshi discovery filter, or the negative-risk book rejection, and the accompanying tests assert that those gates still hold.

## Reproduce

```sh
.venv/bin/pytest -q backend/tests/test_negative_risk.py
```

The test replays recorded payloads, verifies payload digests against the labels, checks the documented conversion arithmetic with `Decimal`, and confirms that the exclusion gates are unchanged.
It makes no network requests.
