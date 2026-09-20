# Backend stream handoff

## Completed

Branch: `backend/27-stream-contract`, based on `origin/main` at `d065906343a3dde228a9068e115c3ff74fa381de`.
Issue: [#27](https://github.com/acheng2007/arbbot/issues/27).
Added exchange-neutral stream models, an asynchronous adapter protocol, bounded order-book state, and deterministic recovery tests.
Documented consumer and adapter obligations in `docs/stream-contract.md`.
Reproduced and fixed a recovery gap where an invalid or oversized discarded delta allowed an older snapshot to restore eligibility.
Such events now require a new subscription epoch.

Validation: Ruff formatting/lint passed; the complete backend suite passed 88 tests against SQLite and 88 against local PostgreSQL.
No network adapter, worker integration, schema change, or frontend change is included.
Hosted CI is pending PR publication.

## Production scope remaining

The full backend production goal remains active and incomplete.
Source artifacts (#45), canonical definitions (#44), fees (#46), catalog filtering (#47), and authentication (#48) are separate review branches.
Authentication hosted run 35538853900 completed successfully at `fbe57e49976ded64645022050e65d9c1e085759a`.
Merge prerequisite interfaces through review before dependent implementation; reconcile sibling migration parents when integrating source storage and catalog filtering.
Venue evidence enrichment, extraction/corpus validation, fee implementations and evaluation integration, database reviews, actual streams, worker integration, observability, and staging/recovery validation remain.
Render and Auth0 were recommended, but no provider selection, account setup, or deployment was authorized by that recommendation alone.
Preserve the original frontend worktree's modified `apps/web/next-env.d.ts` and untracked `.specstory/`.

## Next action

Publish this focused draft PR and inspect its hosted backend checks; then advance independent tracing issue #36 while prerequisite PRs await review.
