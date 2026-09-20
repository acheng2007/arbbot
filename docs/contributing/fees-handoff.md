# Backend fee workstream handoff

The full backend production goal remains active.
This increment implements issue #11 only; exchange policies and engine integration are still required.
Workspace: `/private/tmp/arbbot-backend-fees`.
Branch: `backend/11-fee-contract`, from `origin/main` at `d065906`.

## Completed

Added versioned requests, fill ladders, conservative fee components, quote provenance and expiry, explicit unavailable results, and an asynchronous provider boundary.
Financial inputs reject binary floats and use bounded Decimal values; totals serialize as strings.
Charges round upward at the specified order/fill scope without relying on ambient Decimal precision.
Zero fees require explicit policy evidence rather than a fallback.
Provider results are revalidated and bound to the exact request and evaluation time.
Raw provider errors are suppressed while cancellation propagates.
Existing CostPolicy and engine behavior remain unchanged as required by #11.
See `docs/fee-contract.md` for usage and limitations.

## Validation

Full SQLite suite: 98 passed.
Full PostgreSQL suite: 98 passed using isolated test schemas.
Ruff lint and formatting passed.
Tests cover exact serialization and roundtrip, fixed/quantity/price-dependent components, per-fill rounding, malformed inputs, zero policy requirements, expiry, wrong-request quotes, provider failure, and cancellation.
This interface has no live exchange policy or engine path yet, so its tests do not establish live fee accuracy.

## Related work and CI

Draft PR #44 is canonical settlement definitions on `backend/1-contract-vocabulary` in `/private/tmp/arbbot-backend-contracts`.
Draft PR #45 is source evidence storage on `backend/2-source-artifacts` in `/private/tmp/arbbot-backend-production`.
Both original hosted runs failed because cross-test imports required a test package declaration that local PYTHONPATH masked.
CI logs reproduced the failure; both branches now include `backend/tests/__init__.py` and pass their documented pytest command locally without PYTHONPATH.
Fix commits are `b3a0fff` and `fa24676`; hosted runs 35522827821 and 35522831646 were observed in progress and still require final verification.
Do not infer hosted success from local checks.

Source enrichment, discovery, real-pair validation, expanded extraction, settlement cases, venue fees/slippage, review persistence/auth/API integration, filtering, streaming/recovery, revalidation, observability, deployment, and backup recovery remain unfinished.
The full requirements and dependency map remain in `docs/contributing/README.md`.
Do not merge unreviewed branches or implement dependency-blocked issues as if their bases were merged.

## Next action

Publish this issue as a separate draft PR, verify the corrected hosted CI runs, then implement dependency-free backend market/match filtering (#20) on a new branch.
Venue fee policies (#12/#13) require review/merge of #11 and current exchange documentation before implementation.
