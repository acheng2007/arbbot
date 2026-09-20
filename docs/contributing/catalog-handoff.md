# Backend catalog workstream handoff

The full backend production goal remains active; this increment implements issue #20.
Workspace: `/private/tmp/arbbot-backend-catalog`.
Branch: `backend/20-catalog-filtering`, based on `origin/main` at `d065906`.
Published draft PR: https://github.com/acheng2007/arbbot/pull/47.

## Completed and validation

Moved only the market/match list routes into a catalog router, preserving response lists and default pagination.
Added parameterized SQL filtering for venue/status/family/text and match evidence completeness before pagination.
Added conservative family/evidence projections refreshed by the existing repository write paths and one additive migration with a family pagination index.
Necessary integration edits are repository projection writes, storage model registration, application router wiring, and regenerated OpenAPI.
`docs/catalog-api.md` explains filtering semantics, migration refresh behavior, and limitations.
The test package declaration supports helper imports under the documented pytest invocation, as learned from hosted CI on the earlier PRs.

Full SQLite suite: 90 tests passed.
Full PostgreSQL suite: 90 tests passed in isolated schemas.
Both include migration round trips/schema drift, combined filters, literal search escaping, mode isolation, same-leg matching, stale update rejection, API bounds, and family index query-plan checks.
Ruff lint and formatting pass.
Hosted CI for this branch has not yet been verified.
No frontend implementation or live contract equivalence is claimed.

## Related backend progress

Draft PR #44 contains canonical definitions; draft PR #45 contains source evidence storage.
Both passed hosted CI after adding missing test package declarations.
Draft PR #46 contains fee contracts and passed hosted run 35522949867 at `dae27c3`.
An additional fee bug was reproduced through FeeRequest: the existing adapter's `pUSD` asset was rejected by an uppercase-only pattern.
Commit `ca90c78` preserves mixed-case identifiers, includes a regression test, and passed all 24 focused fee tests; its hosted follow-up still needs verification.
The fee worktree is `/private/tmp/arbbot-backend-fees`.

The source and catalog migrations currently both descend from `a2a3099f82df` because they are independent unmerged PRs.
Before merging the second schema PR, rebase its migration parent onto the reviewed merged revision and recheck the combined migration graph.
Do not merge unreviewed branches.

Source enrichment, supported pair discovery/corpus, expanded extraction, exceptional settlements, exchange fee policies/slippage, reviews/authentication, streams/recovery/revalidation, observability, deployment, and backup rehearsal remain.
Automatic trading, custody, transfers, and private-account access remain out of scope.

## Next action

Verify catalog PR #47 and fee follow-up hosted checks, then implement dependency-free authentication and reviewer authorization (#17) on a new issue branch.
Use `docs/contributing/README.md` for the complete production dependency map.
