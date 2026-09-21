# Canonical settlement vocabulary, version 2

Issue #1 extends evidence-backed contract definitions with precise measurement and settlement fields.
Authors must explicitly set `schema_version` to `2` to use the new fields.
Version 1 remains readable, including files that omit `schema_version`, but cannot establish compatible live settlement under the current comparator.
The existing extraction parser continues to emit legacy partial drafts; this change does not broaden extraction or infer missing facts.

## Required evidence

All existing fields remain required for compatibility.
Version 2 adds the eight fields below, each represented by the existing `Fact` structure with a value, source and verbatim quote.
Settlement facts require rules or settlement-details evidence, never title evidence alone.
Missing fields are shown as unknown in comparison results.
The literal `unknown` also produces an unknown comparison even when both contracts use it.
`not_applicable` is an explicit assertion that requires evidence, not a default for absent information.

| Field | Values and meaning |
| --- | --- |
| `adjustment` | `seasonally_adjusted`, `unadjusted`, `not_applicable`, `unknown` |
| `precision` | Integer decimal-place count from 0 through 28, or `not_applicable` / `unknown`; relates to the measured value in its stated units |
| `rounding` | `half_up`, `half_even`, `floor`, `ceiling`, `truncate`, `none`, `not_applicable`, `unknown` |
| `revision_policy` | `initial`, `latest_at_cutoff`, `final`, `not_applicable`, `unknown`; specifies which publication is authoritative |
| `observation_start` | ISO timestamp with UTC offset, or `not_applicable` / `unknown` |
| `observation_end` | ISO timestamp with UTC offset, or `not_applicable` / `unknown`; cannot precede start |
| `observation_start_inclusive` | `true`, `false`, `not_applicable`, `unknown` |
| `observation_end_inclusive` | `true`, `false`, `not_applicable`, `unknown` |

Version 2 also validates `measurement` as `year-over-year`, `month-over-month`, `level`, `binary`, `not_applicable`, or `unknown`.
`timezone` must identify an IANA timezone, such as `America/New_York` or `UTC`, or explicitly be `not_applicable` / `unknown`.
The existing `value_version` field remains available to identify a particular publication or vintage, while `revision_policy` specifies the selection rule.
`observation_window` remains the evidence-backed window description; the new bounds and inclusivity fields make its endpoints separately comparable.
The existing comparison operator retains the strict-versus-inclusive threshold distinction.

Values are compared conservatively and exactly, except numeric thresholds already use Decimal equality.
Equivalent timestamp spellings, timezone aliases, or precision spellings are not automatically equated.
A conflict requires review rather than silently normalizing potentially material distinctions.
These fields do not implement a new payout engine or prove that the supplied quotations support the reviewer's interpretation.

## Migration and review invalidation

Existing version 1 definitions deserialize without filling new fields, changing their version, or changing the serialized hash input.
They can continue to retrieve same-event candidates, but comparison reports `definition_schema_upgrade_required` and remains incomplete unless there is a conflict.
A legacy approval therefore cannot produce a verified live match or pass the engine's structured-equivalence recheck.
Explicit simulation behavior is unchanged.

To migrate a definition, inspect the original terms, set version 2, and add each new fact only when it has adequate evidence.
Keep absent fields absent or explicitly unknown when supported; never substitute `not_applicable` simply to complete the definition.
Definition hashes include the schema version and all evidence, so upgrading a definition invalidates the old approval hash even when other fields are unchanged.
After completing both definitions and resolving differences, obtain a new review bound to their new hashes through the existing review-file workflow.
No database migration is needed, and historical stored definitions are not rewritten.
Previously stored historical statuses remain historical records; run a worker evaluation cycle to refresh current persisted matches and opportunities under the new comparison rules.

## Validation

The vocabulary tests cover conflict rejection, missing/unknown fields, legacy deserialization, hash changes, stale approvals, invalid values, evidence requirements and engine suppression.
The existing worker-to-database-to-API test now uses complete version 2 definitions.
Extraction tests verify that the new fields remain missing rather than being inferred.
The published definition and OpenAPI schemas are regenerated from the application models.
