# Definition vocabulary version 2

Version 2 makes measurement and observation semantics explicit before live settlement equivalence can be approved.
Set `schema_version` to `2` on new reviewed definitions.
Every fact retains its verbatim evidence quote and source reference.
The generated `docs/definitions.schema.json` publishes the definition structure; the Pydantic model also validates the semantic constraints below.

| Field | Allowed values or representation |
| --- | --- |
| `measurement` | `month-over-month`, `year-over-year`, `level`, `not_applicable` |
| `seasonal_adjustment` | `seasonally_adjusted`, `not_seasonally_adjusted`, `not_applicable` |
| `rounding_increment` | Positive finite decimal string in the measurement's units, `none`, or `not_applicable` |
| `rounding_mode` | `half_even`, `half_up`, `half_down`, `floor`, `ceiling`, `toward_zero`, `away_from_zero`, `none`, `not_applicable` |
| `revision_policy` | `initial_release`, `final_release`, `latest_at_deadline`, `not_applicable` |
| `observation_start`, `observation_end` | ISO datetime with explicit UTC offset, or `not_applicable` |
| `observation_start_inclusive`, `observation_end_inclusive` | `true`, `false`, `not_applicable` |
| `timezone` | IANA timezone identifier, or `not_applicable` |

`unknown` is an explicit unknown value on every fact, including existing fields.
Omitting a fact has the same effect on completeness as marking it unknown.
Two unknowns never establish equality, and any unknown required field prevents compatible settlement status.
`not_applicable` requires evidence just like any other asserted fact; it must not substitute for missing information.
Every version 1 required field remains required in version 2, including source, units, cancellation, payout, exceptional conditions, and the observation-window description.
The existing `value_version` fact retains the specific publication/version interpretation, while `revision_policy` gives its canonical revision-selection policy.
The canonical fields do not replace field-level source interpretation or human review.

Rounding increment and mode must agree when either is `none` or `not_applicable`.
Observation start must precede end, except that an instant with both boundaries included is valid.
An explicitly excluded endpoint on a zero-length interval is invalid.
Naive datetimes are rejected so local-clock ambiguity is not silently resolved.
An actual bound cannot use a `not_applicable` inclusion policy, and an absent bound cannot claim inclusion.
Decimals compare exactly by value, and observation bounds compare by UTC instant.
Original strings and quotes remain intact for audit and hash binding.
Different IANA timezone identifiers conservatively remain different; no alias equivalence is assumed.

## Migration and approval invalidation

Existing version 1 definitions, including documents that omit `schema_version`, remain readable and retain their original serialized shape and hash.
Version 1 can still identify shared events and produce candidates.
It always reports `definition_schema_upgrade_required` and cannot establish compatible live settlement.
New canonical fields cannot be smuggled into version 1 documents.
The existing deterministic parser still produces partial version 1 drafts; it now exposes the additional missing fields without inventing values.

To migrate a definition, verify the current source terms, set version 2, and provide evidence-backed values for all required fields.
There is no automatic conversion that fills missing semantics with defaults.
Changing the version, any value, or evidence changes the definition hash.
Prior reviews continue to bind their original hashes and cannot approve the upgraded interpretation.
A reviewer must issue a new review against both current definition hashes and source terms.
The worker then reevaluates the pair; incomplete or conflicting semantics suppress opportunities even if a review otherwise says verified.
Historical records remain readable and are not rewritten.
The simulation workflow remains explicitly synthetic and is not proof of live equivalence.

## Validation

The vocabulary tests cover monthly/annual differences, adjustment, precision, rounding mode, initial/revised policy, strict/inclusive thresholds, observation intervals, explicit unknowns, old-definition loading and hash stability, and approval invalidation.
An integration test changes seasonal adjustment after publishing an opportunity, runs the ingestion/evaluation cycle again, and confirms through the API that the opportunity disappears and the matching conflict is visible.
The same tests run against both isolated SQLite databases and PostgreSQL schemas.
