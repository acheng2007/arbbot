> Historical snapshot retained during the October 11, 2026 reconciliation.
> Branches, pending states, test counts, and next actions below describe earlier sessions.
> Use the [current handoff](../catalog-handoff.md) and [roadmap](../../implementation-roadmap.md) for active work.

# Backend catalog workstream handoff

The full backend production goal remains active; this increment implements issue #20.
Workspace: `/private/tmp/arbbot-backend-catalog`.
Branch: `backend/20-catalog-filtering`, integrating `origin/main` at `98f2791`.
Published draft PR: https://github.com/acheng2007/arbbot/pull/47.

## Completed and validation

Moved only the market/match list routes into a catalog router, preserving response lists and default pagination.
Added parameterized SQL filtering for venue/status/family/text and match evidence completeness before pagination.
Added conservative family/evidence projections refreshed by the existing repository write paths and one additive migration with a family pagination index.
Necessary integration edits are repository projection writes, storage model registration, application router wiring, and regenerated OpenAPI.
`docs/catalog-api.md` explains filtering semantics, migration refresh behavior, and limitations.
The test package declaration supports helper imports under the documented pytest invocation, as learned from hosted CI on the earlier PRs.

Full SQLite suite after main integration: 122 tests passed.
Full PostgreSQL suite after main integration: 122 tests passed in isolated schemas on a disposable PostgreSQL 17 instance.
Both include migration round trips/schema drift, combined filters, literal search escaping, mode isolation, same-leg matching, stale update rejection, API bounds, and family index query-plan checks.
Ruff lint and formatting pass.
Hosted CI needs verification for this integration commit.
Hosted run 35560695182 failed the pre-existing future-quote test because its timestamp was evaluated at module import and ceased to be future-dated on a slow runner.
Reproduced this with an 11-second collection delay: one failure and two passes.
The test now derives timestamp offsets from the same explicit evaluation instant; all three delayed cases and all 16 engine tests pass.
No production quote freshness rules or assertions were weakened.
This small shared test correction is necessary to verify the integration reliably and is also applied to canonical PR #44.
No frontend implementation or live contract equivalence is claimed.

Reproduced the combined deployment failure through the migration test: `alembic upgrade head` rejected two heads after main's source migration landed.
Resolved the storage import conflict by retaining both source and catalog declarations.
Reparented the unmerged catalog migration onto main's `d0cc5e73c848`; did not modify the landed source migration.
The migration regression now captures source evidence and proves it survives catalog downgrade to the source revision and re-upgrade.
Alembic reports one head, and generated OpenAPI remains unchanged.
The old database service on port 55432 was stopped; the first PostgreSQL attempt failed at connection setup, so validation used a separate temporary database on port 55433.

## Related backend progress

Main contains source storage from a separate implementation and the completed negative-risk assessment (#39).
Use main's source interfaces; PR #45 competes with that implementation and must not be merged blindly.
Source enrichment is in progress on remote branch `data/3-4-source-enrichment`.
Canonical definitions #44, fees #46, authentication #48, streams #49, tracing #50, and CI documentation #51 remain separate PRs.
Tracing hosted run 35540033344 passed at `f94f205ad0b66f41b3472d1aec5df149ffd8f257`.
CI documentation hosted run 35540098757 passed at `e5a64cd0fb252893f06803bd058b640a43cb5bda` before its handoff-only update.
Do not merge unreviewed branches.

Source enrichment, supported pair discovery/corpus, expanded extraction, exceptional settlements, exchange fee policies/slippage, reviews/authentication, streams/recovery/revalidation, observability, deployment, and backup rehearsal remain.
Automatic trading, custody, transfers, and private-account access remain out of scope.

## Next action

Verify the integrated catalog PR #47's hosted checks, then review and reconcile remaining prerequisite branches against current main without duplicating the source-enrichment workstream.
Use `docs/contributing/README.md` for the complete production dependency map.
