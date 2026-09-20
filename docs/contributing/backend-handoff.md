# Backend production workstream

The full objective remains active: complete the entire backend end to end for production, testing every increment.
Neither of the two completed local increments establishes production readiness.

## Workspaces and completed work

- `/private/tmp/arbbot-backend-contracts`, branch `backend/1-contract-vocabulary`: version 2 canonical measurement and settlement vocabulary, conservative unknown handling, legacy-definition loading, review invalidation, regenerated schemas, and migration documentation.
- `/private/tmp/arbbot-backend-production`, branch `backend/2-source-artifacts`: immutable source documents, idempotent captures, explicit retrieval failures, size bounds, database immutability triggers, and additive migration.

Both are focused issue branches; neither is merged into main.
Remote main was fetched at `d065906`, including merged frontend PR #43.
GitHub issues #1, #2, and #11 were verified open and unassigned using the GitHub connector.
The CLI is unavailable, but the connector provides repository access.
The frontend worktree and its user changes remain intact.

## Validation evidence

Canonical-definition branch: 153 tests passed independently on SQLite and PostgreSQL, including worker-to-database-to-API invalidation after seasonal adjustment changes.
Every required field is tested both omitted and explicitly unknown; neither case can establish compatible settlement.
Legacy hashes remain stable, while upgraded definitions require fresh review hashes.
Ruff lint and formatting passed.
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

Publish the two completed increments as separate draft PRs against current main, then implement the dependency-free fee quote interface (#11) on its own branch.
Keep dependent source enrichment and parser work gated on reviewed foundation changes, following CONTRIBUTING.md.
