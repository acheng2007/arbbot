# Structured contract matching

The worker loads evidence-backed contract interpretations from `ARBBOT_DEFINITIONS_FILE` on each cycle.
This is a JSON array validated against [definitions.schema.json](definitions.schema.json).
An interpretation is a proposal, not an equivalence approval.
Automated parsers and LLM extraction are not implemented yet.
The current authoring workflow is a local JSON file and the existing read-only API.

## Authoring and review

1. Fetch each market from `GET /api/v1/markets/{market_id}` and retain its `id` and `terms_hash`.
2. Write a definition containing `market_id`, `terms_hash`, an `extractor` identity or version, and `facts`.
3. Each fact contains a canonical `value`, a `source`, and an exact supporting `quote`.
4. Configure the definitions file in the worker and inspect `GET /api/v1/matches` after a cycle.
5. Check the full original rules, quotations, comparison differences, and exceptional settlement scenarios.
6. For a compatible pair, copy the comparison's `left_hash` and `right_hash` into the review's `left_definition_hash` and `right_definition_hash`, respectively.
7. Supply the remaining review fields, costs, scenarios, reviewer, expiry, and current market terms hashes through `ARBBOT_REVIEWS_FILE`.

Use the match's left/right ordering when authoring a review.
Both files must be readable inside the worker container when running Docker.
An invalid file fails the cycle instead of silently falling back to previously approved definitions.
Existing live reviews without definition hashes now remain candidates until migrated through this workflow.
Simulation fixtures retain their existing explicit simulation approval path.

Example of a partial definition, which intentionally remains incomplete:

```json
[
  {
    "market_id": "replace-with-market-id",
    "terms_hash": "replace-with-current-64-character-terms-hash",
    "extractor": "reviewer-name/manual-v1",
    "facts": {
      "operator": {
        "value": ">",
        "source": "rules",
        "quote": "replace with exact text that establishes a strict inequality"
      }
    }
  }
]
```

The example requires real identifiers, hashes, and evidence before use.
Source can be `title`, `rules`, or `settlement_details`.
For `settlement_details`, also provide `source_key` naming a top-level string field.
Title evidence is permitted only for event identity fields.
The validator checks quotation presence, not whether a quotation logically entails its proposed value.
A human reviewer must assess that interpretation.
External contract documents must be preserved in normalized source data before they can substantiate facts through this interface.

## Canonical fields

| Field | Meaning |
| --- | --- |
| event_type | Event family, such as economic_release |
| entity | Canonical subject or jurisdiction |
| metric | Quantity or event being observed |
| reference_period | Reporting period or unique event occurrence |
| measurement | Exact statistic, including adjustments and aggregation |
| source | Canonical settlement publisher or source |
| value_version | Initial release, revised release, or other publication version |
| operator | `>`, `>=`, `<`, `<=`, `=`, or `binary` |
| threshold | Finite decimal string, or `not_applicable` |
| units | Units of the measured value |
| observation_window | Exact observation bounds; do not substitute trading close |
| timezone | Timezone governing observation and deadlines |
| outcome_orientation | `yes_if_true` or `yes_if_false` |
| payout | Unit payout and complementary YES/NO settlement behavior |
| cancellation | Cancellation and refund policy |
| exceptions | Postponement, ambiguity, correction, and other exceptional rules |

All fields need supporting evidence before comparison is compatible.
Missing fields are unknown, never wildcards.
Use identical canonical values only when their meanings are identical.
Apart from decimal threshold equivalence, comparison is deliberately exact and case sensitive.
Payout describes contract payoff structure; settlement asset conversion remains governed by reviewed cost and payout conversion bounds.
The evaluator still supports only aligned unit binary contracts and the scenarios described in the backend documentation.

## Candidate retrieval and approval

Equal event identity fields produce a stable event key and retrieve a pair even if titles and trading close dates differ.
Title similarity remains a fallback for discovering unstructured candidates.
The comparison reports `compatible`, `conflict`, or `incomplete` with field-level differences and evidence issues.
Compatible means these supplied interpretations agree, not that the software has proved settlement equivalence.
Neither a shared event key nor a compatible comparison automatically verifies a pair.

Live verification requires a current human review, complete compatible definitions, valid quotations, and review hashes binding both exact definitions.
Changing source terms invalidates their definitions and review.
Changing an interpretation or its provenance also invalidates approval through the definition hash.
The evaluator independently repeats the structured approval check.
Published opportunities retain the full comparison, definitions, and quotations for audit.
Current matches expose those details through the existing API and OpenAPI models without a database migration.

The remaining extraction work is category-specific parsers and an evaluated LLM extractor using this schema.
The remaining review interface is a web comparison screen; approval currently uses files.
Scenario completeness remains a human responsibility, and differently modeled exceptional outcomes are conservatively blocked even when a more general portfolio solver might support them.
