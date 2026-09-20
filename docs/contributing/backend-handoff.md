# Backend production workstream

## Objective and workspace

Complete the entire backend end to end for production, testing each increment.
The goal remains active and is not satisfied by the source-storage increment below.
Use `/private/tmp/arbbot-backend-production` for this workstream.
The original workspace remains on `frontend/21-web-foundation` with user changes intact.
Current issue branch: `backend/2-source-artifacts`, based on local `main` at `03b91c2`.
Published draft PR: https://github.com/acheng2007/arbbot/pull/45.
The branch was rebased onto remote main at `d065906` before publication.
No issue has been claimed by comment and no backend branch has been merged.
The GitHub CLI is unavailable, but the GitHub connector works; hosted CI is not yet verified.
Maintain the one-issue-per-PR workflow and do not merge unreviewed branches.

## Completed increment

Implemented issue #2 source-artifact storage with SHA-256 content digests, market/mode/venue association, bounded binary content, retrieval timestamps, explicit failure codes, and immutable history.
Separate captures preserve repeat retrievals without duplicating document bytes.
Concurrent identical retries are idempotent.
An additive migration installs database triggers preventing updates and deletes of source artifacts and captures.
The repository rejects absent markets and mismatched venues.
Exchange fetchers and review/parser integration have not been implemented.
See `docs/source-evidence.md` for limits and operational requirements.

## Validation evidence

Original baseline: 75 backend tests passed.
Updated full suite: 87 tests passed with SQLite and independently 87 with PostgreSQL.
New coverage includes concurrent retries, changed document versions, explicit failed retrievals, mode isolation, invalid/oversized evidence, migration upgrades/downgrades, schema drift, and database mutation rejection.
Ruff lint and format checks passed.
Docker Compose rebuilt and started API, worker, migration service, and PostgreSQL from this worktree.
The running simulation smoke test passed before and after the increment: PostgreSQL, worker, REST, audit records, and SSE.
`docker compose exec -T api alembic check` reports no new upgrade operations.
No live source-evidence ingestion, hosted CI, or production deployment has been verified.

Commands use the existing virtual environment with `PYTHONPATH=backend` to load this worktree rather than its editable installation in the original workspace.

```sh
PYTHONPATH=backend /Users/adam/Project/arbbot/.venv/bin/pytest -q backend/tests
PYTHONPATH=backend ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot /Users/adam/Project/arbbot/.venv/bin/pytest -q backend/tests
/Users/adam/Project/arbbot/.venv/bin/ruff check backend
/Users/adam/Project/arbbot/.venv/bin/ruff format --check backend
docker compose exec -T api python scripts/smoke.py
docker compose exec -T api alembic check
```

Docker Compose uses the existing `arbbot` local project and its simulation database.
The running containers now use this worktree's backend build.
Migration roundtrip tests use isolated schemas or temporary SQLite files, never application tables.

## Remaining production gates

- Canonical measurement/settlement vocabulary (#1), source enrichment (#3, #4), supported event discovery (#5), positive and negative labeled pairs (#6), expanded extraction (#7, #8), and the offline extraction evaluation (#9).
- Complete exceptional settlement validation (#10), exchange fee interfaces and policies (#11-#14), and integrated slippage modeling (#15).
- Persistent drafts/reviews (#16), authentication/authorization (#17), concurrent-edit-safe review APIs (#18), database approval integration (#19), and search/filtering (#20).
- Streaming contracts and exchange adapters (#27-#29), worker lifecycle/recovery (#30), and opportunity revalidation (#31).
- Hosted backend CI verification (#32), backend coverage supporting the full review-to-opportunity workflow (#33), worker metrics/alerts/tracing (#34-#36).
- Reproducible staging and secrets configuration (#37), deployment validation, database role restrictions, and backup/recovery rehearsal (#38).
- Negative-risk research (#39) without enabling unsupported contracts; execution readiness (#40) stays deferred because this goal does not authorize trading or private account access.

Production completion requires evidence against every applicable gate, including real supported contract pairs and deployment/recovery checks.
A profitable live price discrepancy is not a requirement and must not be fabricated.
Frontend implementation remains a separate workstream; backend API and end-to-end contract coverage must support its integration.

## Next action

Issue #1 is now implemented separately in `/private/tmp/arbbot-backend-contracts`, branch `backend/1-contract-vocabulary`, draft PR https://github.com/acheng2007/arbbot/pull/44.
That branch passes 153 tests on SQLite and PostgreSQL and documents the versioned vocabulary and review invalidation.
The next action is issue #11, the independent fee quote interface, on a branch from `origin/main`; also inspect hosted CI for both drafts.
Issues #1, #2, and #11 were verified open and unassigned through the connector.
Use the contracts worktree handoff for the latest combined progress.
