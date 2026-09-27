# Polymarket fee policy

`fees/polymarket.py` implements the shared `FeeProvider` interface using observed market-specific Gamma metadata.
It is not yet connected to the evaluation engine; existing opportunity calculations still use reviewed fee bounds.

The supported policy uses the market's rate with quantity times price times one minus price, with exponent exactly one.
This follows the current [fee formula](https://docs.polymarket.com/trading/fees) and [market-specific fee fields](https://docs.polymarket.com/market-data/market-details).
Rates are never inferred from a category name.
Unknown exponents, non-taker-only schedules, unsupported instruments, missing flags and contradictory disabled-fee metadata return unavailable results.
Negative-risk support is unchanged.

Explicit `feesEnabled=false` permits zero fees only when no contradictory nonzero schedule is present.
An observed taker-only schedule permits a zero maker trade fee.
Every zero result carries a reason and the observed payload digest; rebates are not deducted from costs.

The documented fee precision is five decimal places.
This implementation rounds upward at every supplied fill boundary to provide a conservative bound for those fills, including when an exchange-rounded tiny fee might instead be zero.
It does not claim that an order-book price level is one actual exchange fill.
Engine integration must account for additional fragmentation before using these values as execution cost bounds.

Requests use the adapter's `pUSD` settlement unit, consistent with the [documented collateral wrapper](https://docs.polymarket.com/concepts/pusd).
Conversion to dollars, venue access and stablecoin exposure remain separate evaluation assumptions.
No wrapping, transfers or trading are performed.

Snapshots bind the market, data mode, instrument support, fee flags, schedule, observation time, effective time, expiration and payload digest.
The default lifetime is five minutes, capped at fifteen minutes; expired or future observations cannot price a request.
Use the exchange HTTP helper's exact JSON parsing when constructing snapshots: numeric financial tokens are preserved as strings, and binary float rates are rejected.
The provider is deterministic after snapshot construction and makes no network calls during calculation.

Two unchanged public responses are retained in `backend/tests/fixtures/polymarket_fees/recorded.json`, with capture URLs and timestamps.
Tests pin their canonical payload digests and cover documented examples, quantity and price boundaries, maker behavior, per-fill rounding, mode/market/unit isolation, expiration, unsupported schedules and explicit fee-free configurations.
Fee-free and malformed metadata variants are synthetic tests, not altered live fixture claims.

Run `.venv/bin/pytest -q backend/tests/test_polymarket_fees.py backend/tests/test_fee_contract.py`.
Next integrate bounded metadata refresh, persisted fee evidence and both venue providers with depth-dependent evaluation.
