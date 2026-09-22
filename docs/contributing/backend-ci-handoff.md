# Hosted backend CI handoff

## Latest main reconciliation

The user authorized reviewing and merging passing foundation PRs #44 and #46 through #51.
PRs #44 and #47 have landed; this branch now integrates main `f91a639a809db8c6562b1793028aa693d7e97f3f`.
This remains a documentation-only PR; no behavior changed during main integration.
Authentication and tracing API conflicts were resolved additively in their respective branches, and authentication's OpenAPI was regenerated from code.
Docker Desktop is manually paused, so no new local PostgreSQL result is claimed for this reconciliation.
Earlier database results remain recorded below; the new head requires hosted PostgreSQL, migration and schema checks.
Next action: verify the new hosted run, then perform the authorized merge without duplicating externally completed merges.
The backend production goal remains incomplete; durable reviews, venue policies and streams, and production validation follow the foundation merges.

## Completed

Branch: `backend/32-hosted-ci-evidence`, based on `origin/main` at `d065906343a3dde228a9068e115c3ff74fa381de`.
Issue: [#32](https://github.com/acheng2007/arbbot/issues/32).
Draft PR: [#51](https://github.com/acheng2007/arbbot/pull/51).
Added `docs/ci.md` with an inspected hosted run, job output, all required backend gates, and maintainer instructions for required checks.
No workflow coverage, assertions, repository protections, or product behavior changed.
Evidence: [run 35539470739](https://github.com/acheng2007/arbbot/actions/runs/35539470739), job 106154402965, stream PR #49 at `0232aefe54c3346bab9a6742a3d7be3545698415`.
All required steps passed, including 89 tests on each database and migration/schema checks.
Recorded extraction coverage remains incomplete: 14 correct fields out of 63 labeled, with zero incorrect fields.
No code tests were rerun solely for this documentation change.
This documentation branch also passed hosted run 35540098757 at `e5a64cd0fb252893f06803bd058b640a43cb5bda`.

## Pending production work

Tracing PR [#50](https://github.com/acheng2007/arbbot/pull/50) passed hosted run 35540033344 at `f94f205ad0b66f41b3472d1aec5df149ffd8f257`.
Main advanced to `98f2791` with independently implemented source storage (`d0cc5e73c848`) and the negative-risk assessment (#39 is closed).
Use the landed source interface; PR #45 is now a competing implementation and must not be merged blindly.
Catalog PR #47 needs migration-parent reconciliation against the landed source revision.
The full backend production goal remains active and incomplete.
Venue enrichment, supported real pairs, fee policies/integration, durable reviews, live stream adapters/integration, dashboards, staging identity/collector verification, and recovery rehearsal remain outstanding.
Preserve the original frontend worktree's modified generated file and untracked `.specstory/`.

## Next action

Update catalog PR #47 against current main and verify the combined migration graph and backend suite; source enrichment is already underway on remote branch `data/3-4-source-enrichment`.
