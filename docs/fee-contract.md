# Fee quote contract, version 1

`FeeRequest` identifies mode, venue, market, outcome, buy/sell direction, maker/taker liquidity, settlement asset, quantity, and the exact fill ladder.
Prices are per contract in the specified settlement asset for binary contracts paying one unit.
Fill quantities must sum exactly to the requested quantity.
Financial inputs accept decimal strings, Decimal objects, or integers; floats and booleans are rejected.
Amounts are finite, nonnegative, bounded to 30 digits and 12 decimal places; quantities and rounding increments must be positive.

`FeeQuote` binds the entire request to source provenance, a policy version, observed/effective/expiry timestamps, and explicit charges.
Each charge represents a fixed, quantity-dependent, or price-dependent amount already calculated by the venue policy implementation.
It specifies order-level or individual-fill scope and a positive rounding increment in settlement-asset units.
Rounding always goes upward to the next increment, giving a conservative charge envelope rather than assuming rebates or favorable rounding.
For example, an amount of 0.051 with increment 0.05 produces 0.10.
Each fill-scoped component rounds separately before the total is summed.
Charges are additive and must not duplicate the same name and fill index.
This interface represents calculated charges; it does not implement exchange formulas or infer a policy from a title.

A quote cannot use future observations, a policy not yet effective, or an expired policy.
Zero fees require a nonempty charge list with explicit zero amounts and a verified zero-fee reason.
There is no implicit zero-cost fallback.
`FeeUnavailable` carries a structured reason and no total: unsupported, stale, not yet effective, missing policy, provider error, or invalid quote.
It must suppress fee-dependent executable estimates until the caller obtains a valid policy.

Providers implement the asynchronous `FeeProvider.quote` protocol and explicitly return unavailable results for unsupported or stale policies.
Call through `quote_fees` to revalidate provider outputs, including nested model instances, and reject quotes bound to another request or time.
Provider exceptions become unavailable results without exposing raw exception text; cancellation propagates.
The caller must supply an aware evaluation timestamp and reevaluate as the request or policy expires.
Downstream components must not reuse a quote for a different fill ladder, venue, side, liquidity assumption, mode, or settlement asset.

Normal JSON output includes derived rounded charges and totals as strings.
For persistence and model reloading, use `model_dump_json(round_trip=True)` so derived fields are recalculated on load rather than trusted as input.
Version 1 has no exchange calls, engine integration, or database migration.
The existing reviewed CostPolicy remains unchanged until the separate fee-integration issue is implemented and tested.
