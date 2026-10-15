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

Canonical definitions now include a settlement-policy inventory covering cancellation, fallback and ambiguous resolution.
Each policy has a source-backed evidence quote and a status: modeled, not applicable or unknown.
Modeled policies enumerate named conditions with a trigger and explicit fixed YES/NO payouts.
Not-applicable declarations also require evidence; they are reviewer interpretations, not automatic conclusions from missing text.
Missing or unknown policies prevent live verification.

Reviews map every modeled condition on each venue to one or more named scenarios.
Validation rejects absent mappings, unknown conditions, duplicate mappings, missing scenario references and disagreement between condition payouts and scenario payouts.
Rules evidence is checked against the exact market terms, and the policy inventory is included in the canonical definition hash.
Adding this field changes definition hashes, including legacy definitions parsed with an absent inventory.
Existing approvals therefore require renewed review after completing the inventory and mappings.

These checks establish coverage of the declared inventory, not semantic completeness of the source interpretation or all joint outcomes.
Reviewers must identify every relevant clause and all reachable combinations of conditions across venues.
The remaining settlement work must validate this workflow against recorded supported real pairs and account for interactions between exceptional conditions.
Matching scenario names or providing two ordinary outcomes does not prove that all settlement outcomes have been covered.
