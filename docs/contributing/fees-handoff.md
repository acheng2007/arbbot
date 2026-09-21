# Backend fee workstream handoff

## Current integration review, 2026-09-21

Integrated main at `98f2791632389523cbf93bfb591e69267fd82b3e`, including the landed source-storage interface and completed negative-risk assessment.
No integration conflicts or new product behavior were introduced.
Applied the shared future-quote test correction already reproduced with delayed collection in PRs #44/#47.
All 131 tests passed on SQLite and 131 on isolated PostgreSQL 17; Ruff lint and format checks passed.
These results include the existing foundation tests together with main's source and negative-risk coverage.
Hosted checks must verify the new integration commit before merge.
The previous PostgreSQL service remains stopped; tests used a disposable instance on port 55433.

Merge authorization for foundation PRs #44 and #46 through #51 remains pending.
Source PR #45 is excluded because a separate source implementation already landed in main.
Next action: verify #46's new hosted checks, finish its review, and merge only after authorization; then advance venue-specific fee policies #12/#13.
The full backend production goal remains active and incomplete.
The historical details below are superseded where this update gives a newer base, validation result, or next action.

The full backend production goal remains active.
This increment implements issue #11 only; exchange policies and engine integration are still required.
Workspace: `/private/tmp/arbbot-backend-fees`.
Branch: `backend/11-fee-contract`, from `origin/main` at `d065906`.
Published draft PR: https://github.com/acheng2007/arbbot/pull/46.

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
Hosted fee run 35522949867 succeeded at `dae27c3`.
Subsequent adapter-contract inspection found that the fee asset pattern rejected the existing `pUSD` identifier.
Reproduced the validation failure directly through FeeRequest, then allowed case-preserving alphanumeric asset identifiers and added a regression test.
This follow-up requires hosted CI revalidation.
Ruff lint and formatting passed.
Tests cover exact serialization and roundtrip, fixed/quantity/price-dependent components, per-fill rounding, malformed inputs, zero policy requirements, expiry, wrong-request quotes, provider failure, and cancellation.
This interface has no live exchange policy or engine path yet, so its tests do not establish live fee accuracy.

## Related work and CI

Draft PR #44 is canonical settlement definitions on `backend/1-contract-vocabulary` in `/private/tmp/arbbot-backend-contracts`.
Draft PR #45 is source evidence storage on `backend/2-source-artifacts` in `/private/tmp/arbbot-backend-production`.
Both original hosted runs failed because cross-test imports required a test package declaration that local PYTHONPATH masked.
CI logs reproduced the failure; both branches now include `backend/tests/__init__.py` and pass their documented pytest command locally without PYTHONPATH.
Fix commits are `b3a0fff` and `fa24676`; hosted runs [35522827821](https://github.com/acheng2007/arbbot/actions/runs/35522827821) and [35522831646](https://github.com/acheng2007/arbbot/actions/runs/35522831646) completed successfully.
The connector confirmed every substantive job step passed: lint/format, SQLite, PostgreSQL, migrations, recorded corpus, and published schema drift.
These are direct hosted CI evidence for PRs #44 and #45; fee PR #46 still requires hosted verification.
Do not infer hosted success from local checks.

Source enrichment, discovery, real-pair validation, expanded extraction, settlement cases, venue fees/slippage, review persistence/auth/API integration, filtering, streaming/recovery, revalidation, observability, deployment, and backup recovery remain unfinished.
The full requirements and dependency map remain in `docs/contributing/README.md`.
Do not merge unreviewed branches or implement dependency-blocked issues as if their bases were merged.

## Next action

Implement dependency-free backend market/match filtering (#20) on a new branch from current remote main, and verify fee PR #46 hosted CI.
Venue fee policies (#12/#13) require review/merge of #11 and current exchange documentation before implementation.
