# Branch consolidation handoff

## Status: October 15, 2026

Target branch: `main`.
Integration branch: `chore/consolidate-main`.
Application baseline: `51a9a21`, the completed `backend/completion` branch with automatic discovery, the redesigned UI, documentation, and the live Jev benchmark.
The current remote main at `aacc456` is already an ancestor of this baseline.
The user authorized merging completed branches and removing them for repository organization.

## Prepared integration

Merged `frontend/regenerate-api-client` at `a0eb55a`, preserving the newer generated schema, expanded client tests, and current handoff because they already include the older PR #56 fix.
Retained the histories of `backend/2-source-artifacts` at `fa24676`, `data/3-4-source-enrichment` at `e089cd8`, and local `backend/16-review-storage` at `7606420` using an explicit history-only merge.
Their integrated replacements already exist in the landed source repository, current enrichment modules, source tests, and `ce70c95`.
The alternate `fdba615a5e84` and `b73c12904a61` migrations must not be restored alongside the current `d0cc5e73c848` lineage.
All original commits and human authorship remain in ancestry.
The application tree after the history merges is byte-for-byte identical to `51a9a21`.
Hosted browser validation then exposed a test navigation race, corrected by waiting for the destination URL and comparison-only link before opening a disclosure shared with the previous route.
Only test synchronization and this organization handoff differ from that application baseline; production behavior is unchanged.

All other existing local and remote branch heads were verified as ancestors of the consolidated history.
This covers the historical backend foundation branches, data source branch, live-price demo, frontend foundation/read-only/CI branches, and frontend workstream.
Stale worktree registrations pointed to deleted temporary directories and were pruned; no live user checkout was removed.
The user's staged research, untracked fee module, browser/session artifacts, and ignored root `.env` remain outside the integration.

## Validation and cleanup

Consolidation PR: [#57](https://github.com/acheng2007/arbbot/pull/57).
The initial hosted frontend generated-client, lint, type, unit, and production-build job passed.
The browser job passed 65 of 66 tests and failed the mobile review-evidence navigation assertion.
The downloaded trace proves the click occurred on the old opportunity URL before comparison navigation finished; the failure screenshot was inspected.
The test now waits for the destination URL and a comparison-only link, retaining all evidence assertions.
The corrected scenario passed ten local runs across desktop and mobile, with two concurrent workers.
Require current hosted backend/frontend checks before merging.
The checks cover both database suites, migrations, schema drift, generated contracts, frontend units/types/lint/build, and desktop/mobile fixture browsers.
The earlier implementation results remain documented at their original scope; they are not substituted for the consolidation head's checks.
After merge, verify each branch head is reachable from remote main before deleting its remote or local ref.
Close or remove superseded PR branches only after their histories are retained.
Switch the original checkout to updated main without stashing or committing unrelated local changes, then remove the temporary integration worktree.
Do not force-push main or discard unmerged commits.

## Next action

Complete hosted validation, merge the consolidation PR into main, and delete only branch heads proven to be ancestors of the merged main.
