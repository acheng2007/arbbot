# Settlement payout validation

Every live review scenario must explicitly provide `left_yes`, `left_no`, `right_yes` and `right_no` as exact decimal strings.
The supported model is a unit-payout binary contract: YES and NO payouts must sum to one separately at each venue.
Fixed fractional settlements such as 0.5/0.5 are representable.
Non-complementary settlements and purchase-price-dependent refunds are unsupported and rejected rather than converted into winning NO positions.

Older review files with only YES payouts remain readable for migration and simulation.
They cannot verify a live match, authorize a durable live approval or produce live opportunities.
Reviewers must supply both NO payouts explicitly after inspecting settlement terms.
The synthetic simulation fixture supplies explicit payouts, including its synthetic cancellation policy.
These fixture values are not exchange policy assumptions.

The evaluator calculates both trade directions against every supplied scenario and uses the lowest combined payout.
A divergent fallback can make the purchased YES on one venue and NO on the other both lose, removing an apparent price discrepancy from opportunities.
Live gates are checked during matching, durable review writes, approval eligibility reads and evaluation, including previously persisted verified matches.

This validates payout arithmetic, not completeness of the scenario set.
The remaining settlement work must bind cancellation, fallback and ambiguous-resolution conditions from source-backed definitions to named reviewed scenarios, reject unmodeled conditions, and validate supported real pairs against recorded source rules.
Matching scenario names or providing two ordinary outcomes does not prove that all settlement outcomes have been covered.
