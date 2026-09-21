# Backend production workstream

## Current integration update, 2026-09-21

PR #44 on `backend/1-contract-vocabulary` now integrates main at `98f2791632389523cbf93bfb591e69267fd82b3e`, including landed source storage and the negative-risk assessment.
The integration had no conflicts and changes no source-storage behavior.
Reviewed comparison and validation paths for missing fields, legacy loading, exact numeric/instant comparison, and stale review invalidation.
All 185 backend tests passed on SQLite and isolated PostgreSQL 17, including worker/database/API invalidation when settlement semantics change.
Ruff lint/format passed; regenerated OpenAPI and definition schemas match committed files.
Hosted validation is required for this new integration commit.
The catalog hosted run exposed a shared future-quote test using an import-time timestamp.
An 11-second collection delay reproduced its failure; the same delay passes after deriving timestamp offsets from a single explicit evaluation instant.
Applied that shared test-only correction here as well; all 16 engine tests pass and financial behavior is unchanged.
Synthetic tests do not establish real cross-exchange equivalence.

Main's source implementation is commit `c07ebb6`, migration `d0cc5e73c848`; use its interface.
PR #45 is now a competing source implementation and must not be merged blindly.
Source enrichment is underway on remote branch `data/3-4-source-enrichment`; issue #39 is completed in main.
Catalog PR #47 integrated the landed source migration and passed 122 tests on each database; hosted run 35560695182 at `b3e83aadd0dfd354237683dbc824c36a8b58e82b` was last observed in progress.
Fee contracts #46, authentication #48, streams #49, tracing #50 and CI documentation #51 are separate prerequisite PRs.
The temporary PostgreSQL instance used port 55433; the old service on 55432 is stopped.

Next action: verify hosted checks on the integrated PR #44, then complete its review/merge prerequisite before implementing durable reviews (#16) against version 2 and the landed source interface.
The full backend goal remains incomplete, including real contract evidence, fee integration, reviews, actual streams, operational monitoring, staging and recovery validation.

## Historical foundation handoff

The following records the initial publication state; the current update above supersedes its next action and dependency status.

The full objective remains active: complete the entire backend end to end for production, testing every increment.
Neither of the two completed local increments establishes production readiness.

## Workspaces and completed work

- `/private/tmp/arbbot-backend-contracts`, branch `backend/1-contract-vocabulary`: version 2 canonical measurement and settlement vocabulary, conservative unknown handling, legacy-definition loading, review invalidation, regenerated schemas, and migration documentation.
- `/private/tmp/arbbot-backend-production`, branch `backend/2-source-artifacts`: immutable source documents, idempotent captures, explicit retrieval failures, size bounds, database immutability triggers, and additive migration.

Both are focused issue branches; neither is merged into main.
Published draft PRs: [#44](https://github.com/acheng2007/arbbot/pull/44) for definitions and [#45](https://github.com/acheng2007/arbbot/pull/45) for source evidence.
Both branches were rebased onto current remote main before publication; upstream changes were frontend/documentation only.
Remote main was fetched at `d065906`, including merged frontend PR #43.
GitHub issues #1, #2, and #11 were verified open and unassigned using the GitHub connector.
The CLI is unavailable, but the connector provides repository access.
The frontend worktree and its user changes remain intact.

## Validation evidence

Canonical-definition branch: 153 tests passed independently on SQLite and PostgreSQL, including worker-to-database-to-API invalidation after seasonal adjustment changes.
Every required field is tested both omitted and explicitly unknown; neither case can establish compatible settlement.
Legacy hashes remain stable, while upgraded definitions require fresh review hashes.
Ruff lint and formatting passed.
Hosted run 35522583045 failed collecting `tests.test_contracts` because tests lacked a package declaration; local PYTHONPATH had masked this.
Added `backend/tests/__init__.py` so the documented pytest command discovers shared helpers without that environment override; hosted revalidation is pending.
OpenAPI and definition schemas were regenerated; the review schema was regenerated and unchanged.
Recorded corpus replay remains 14 correct fields, zero incorrect, across nine fixtures and 63 labels.
No live-equivalence claim follows from the synthetic integration tests.

Source branch: 87 tests passed on SQLite and PostgreSQL, including migration round trips, drift checks, concurrent retries, and database mutation rejection.
The rebuilt source branch passed the running Docker simulation smoke test through PostgreSQL, worker, REST, audit history, and SSE.
Docker Compose currently runs the source-storage branch, not the canonical-definition branch.

Use `PYTHONPATH=backend` with `/Users/adam/Project/arbbot/.venv/bin/pytest -q backend/tests` in the appropriate worktree.
For PostgreSQL add `ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot`; tests create isolated schemas.

## Remaining gates

Source enrichment (#3/#4), supported overlapping discovery (#5), labeled cross-exchange pairs (#6), venue extraction (#7/#8), and offline extraction evaluation (#9) remain.
Exceptional settlements (#10), fee contracts and policies (#11-#14), and slippage (#15) remain.
Persistent reviews (#16), authentication/authorization (#17), review APIs (#18), approval integration (#19), and filtering (#20) remain.
Streams and recovery (#27-#30), immediate revalidation (#31), hosted CI evidence (#32), and integrated workflow QA (#33) remain.
Worker metrics, dashboards, alerts, and tracing (#34-#36), staging/secrets/deployment (#37), and backup/recovery rehearsal (#38) remain.
Negative-risk assessment (#39) must not enable unsupported instruments without validation.
Automatic trading, custody, transfers, and private account access remain out of scope; #40 is deferred.
Actual production environment selection and deployment verification are not yet established.
Do not mark the goal complete until all applicable requirements have direct evidence.

## Next action

Implement the dependency-free fee quote interface (#11) on its own branch from `origin/main`, and inspect hosted CI on the two published PRs.
Keep dependent source enrichment and parser work gated on reviewed foundation changes, following CONTRIBUTING.md.
