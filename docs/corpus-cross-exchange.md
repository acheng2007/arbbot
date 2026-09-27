# Supported cross-exchange corpus

`backend/tests/fixtures/cross_exchange/recorded.json` contains eight unchanged public market responses, each with its source URL and capture timestamp.
`labels.json` binds source-reading regression labels to exact payload digests.
These labels were derived from reading the contract text, not copied from an extraction report, and are not human settlement approvals.
They cover three families: Fed rate hikes, recession and Treasury yields.
All eight instruments satisfy the existing adapter support checks; instrument support does not imply settlement equivalence or current executable liquidity.

| Pair | Candidate interpretation | Material difference |
| --- | --- | --- |
| Kalshi `KXFEDHIKE-2-26DEC31` / Polymarket `4620900` | Same broad US Fed rate-hike event, terminal year 2026 | Issuance through December 31 versus September 17 through the December FOMC decision; target range/level versus upper bound |
| Kalshi `KXFEDHIKE-2-27DEC31` / Polymarket `4620900` | Different terminal year | 2027 versus 2026 |
| Kalshi `KXRECSSNBER-26` / Polymarket `609655` | Different recession triggers | BEA consecutive GDP quarters versus GDP or an NBER announcement |
| Kalshi `KXRECSSNBER-27` / Polymarket `609655` | Different period and triggers | Q4 2026 through Q4 2027 versus the earlier GDP/NBER conditions |
| Kalshi `KXUST10AM-26SEP30-T5.20` / Polymarket `4890276` | Same broad Treasury-yield event in September 2026 | One date versus any date in an interval; strict greater-than versus greater-than-or-equal |

The supported same-event milestone now has positive candidate evidence.
No pair in this corpus is labeled settlement-compatible, and the reviewed-live-pair milestone remains open.
The broad identity tuple groups related events for inspection; measurement and window differences still prevent verification.

The recession records expose source and exceptional-settlement differences that titles and tickers hide.
Kalshi's `NBER` ticker text does not establish an NBER payout trigger: its recorded rule names BEA GDP quarters.
Polymarket permits an NBER announcement, accepts revised preceding-quarter GDP estimates, and has a fallback based on available releases if Q4 data has not arrived by its June 30, 2027 deadline.
The Treasury Polymarket record instead has a fixed NO fallback if no qualifying value appears and the final date's data remains unavailable at its October 14 deadline.
Kalshi's expiry wording alone does not establish that same fallback payout.
All these statements describe the captured payloads; capture URLs are recorded alongside each original response.

The existing `fixtures/contracts` corpus retains foreign-jurisdiction CPI and source-publisher negatives; those Polymarket CPI instruments remain unsupported negative-risk markets.
No negative-risk restriction was relaxed to obtain these pairs.
Full linked rules, supplemental clarifications and reviewer-confirmed completeness are still required for live approval.

Offline validation checks payload digests, source timestamps, adapter normalization, quote provenance, same-event labels and exact conflict fields.
The Fed parser is separately tested against the source-reading labels and refuses to identify the event from a title alone or from a rate-decrease condition.
It proposes partial definitions only and does not invent payout, source or cancellation policies.
The default catalog now searches the Fed rate-hike family alongside CPI so these supported candidates can reach the interface.

Run the corpus checks with `.venv/bin/pytest -q backend/tests/test_cross_exchange_corpus.py`.
