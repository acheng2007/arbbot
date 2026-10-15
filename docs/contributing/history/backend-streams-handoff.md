> Historical snapshot retained during the October 11, 2026 reconciliation.
> Branches, pending states, test counts, and next actions below describe earlier sessions.
> Use the [current handoff](../backend-streams-handoff.md) and [roadmap](../../implementation-roadmap.md) for active work.

# Backend stream handoff

## Latest main reconciliation

The user authorized reviewing and merging passing foundation PRs #44 and #46 through #51.
PRs #44 and #47 have landed; this branch now integrates main `f91a639a809db8c6562b1793028aa693d7e97f3f`.
All 214 SQLite tests and Ruff lint/format checks passed with the newly landed canonical definitions and catalog filtering.
Authentication and tracing API conflicts were resolved additively in their respective branches, and authentication's OpenAPI was regenerated from code.
Docker Desktop is manually paused, so no new local PostgreSQL result is claimed for this reconciliation.
Earlier database results remain recorded below; the new head requires hosted PostgreSQL, migration and schema checks.
Next action: verify the new hosted run, then perform the authorized merge without duplicating externally completed merges.
The backend production goal remains incomplete; durable reviews, venue policies and streams, and production validation follow the foundation merges.

## Current integration review, 2026-09-21

Integrated main at `98f2791632389523cbf93bfb591e69267fd82b3e`, including the landed source-storage interface and completed negative-risk assessment.
No integration conflicts or new product behavior were introduced.
Applied the shared future-quote test correction already reproduced with delayed collection in PRs #44/#47.
All 121 tests passed on SQLite and 121 on isolated PostgreSQL 17; Ruff lint and format checks passed.
These results include the existing foundation tests together with main's source and negative-risk coverage.
Hosted checks must verify the new integration commit before merge.
The previous PostgreSQL service remains stopped; tests used a disposable instance on port 55433.

The user explicitly authorized reviewing and merging passing foundation PRs #44 and #46 through #51.
Source PR #45 is excluded because a separate source implementation already landed in main.
Next action: verify #49's new hosted checks, finish its review, and merge only after authorization; then advance venue stream adapters #28/#29.
The full backend production goal remains active and incomplete.
The historical details below are superseded where this update gives a newer base, validation result, or next action.

## Completed

Branch: `backend/27-stream-contract`, based on `origin/main` at `d065906343a3dde228a9068e115c3ff74fa381de`.
Issue: [#27](https://github.com/acheng2007/arbbot/issues/27).
Draft PR: [#49](https://github.com/acheng2007/arbbot/pull/49).
Added exchange-neutral stream models, an asynchronous adapter protocol, bounded order-book state, and deterministic recovery tests.
Documented consumer and adapter obligations in `docs/stream-contract.md`.
Reproduced and fixed a recovery gap where an invalid or oversized discarded delta allowed an older snapshot to restore eligibility.
Such events now require a new subscription epoch.
Rejected snapshots also advance the recovery sequence floor, preventing rollback after a level-limit rejection.

Validation: Ruff formatting/lint passed; the complete backend suite passed 89 tests against SQLite and 89 against local PostgreSQL, including the additional snapshot-rejection regression.
No network adapter, worker integration, schema change, or frontend change is included.
Hosted run 35539388560 is in progress for initial commit `d18810d82e34eb99d8799f8e759687ecbe706fda`; inspect the subsequent head run after the recovery follow-up is pushed.

## Production scope remaining

The full backend production goal remains active and incomplete.
Source artifacts (#45), canonical definitions (#44), fees (#46), catalog filtering (#47), and authentication (#48) are separate review branches.
Authentication hosted run 35538853900 completed successfully at `fbe57e49976ded64645022050e65d9c1e085759a`.
Merge prerequisite interfaces through review before dependent implementation; reconcile sibling migration parents when integrating source storage and catalog filtering.
Venue evidence enrichment, extraction/corpus validation, fee implementations and evaluation integration, database reviews, actual streams, worker integration, observability, and staging/recovery validation remain.
Render and Auth0 were recommended, but no provider selection, account setup, or deployment was authorized by that recommendation alone.
Preserve the original frontend worktree's modified `apps/web/next-env.d.ts` and untracked `.specstory/`.

## Next action

Verify hosted backend checks on PR #49's latest commit, then advance independent tracing issue #36 while prerequisite PRs await review.
