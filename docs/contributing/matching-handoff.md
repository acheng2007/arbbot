# Matching workstream handoff

## Review delivery

Issue #1 implementation is on branch `matching/1-canonical-definitions`, based on main at `d008e49`.
Working checkout: `../arbbot-contracts` relative to the original repository.
Issue #2 remains untouched and uncommitted in `../arbbot` on `data/2-settlement-source-artifacts`.

Added explicit version 2 definitions with measurement adjustment, precision, rounding, revision policy, observation bounds and inclusivity, and timezone validation.
Legacy version 1 definitions remain readable and usable for candidate retrieval but cannot establish current live equivalence.
Missing and explicit unknown values cannot establish compatibility.
Upgraded definitions require new hash-bound approvals.
No parser expansion, API endpoint, database migration or frontend change was included.

Validation: all 139 backend tests passed on SQLite, including the existing worker/database/API workflow and new vocabulary tests.
Backend lint, formatting and diff whitespace checks passed.
Definition, review and OpenAPI schemas were regenerated; review schema content was unchanged.
PostgreSQL tests remain pending because no PostgreSQL or Docker executable was available in this environment.
Current GitHub issue status and ownership remain unverified from the prior access limitation.

## Next action

Have the user review issue #1 in this checkout and issue #2 in its separate checkout before committing either.
All changes, including handoffs, are intentionally uncommitted under the user's explicit instruction to commit only after review.
No push, PR or issue comment was created.
After review, verify PostgreSQL checks and use the user's configured Git identity for separate issue commits.
Source enrichment issues #3 and #4 should follow the source-storage baseline after approval; preserve the Kalshi group-evidence follow-up as a separate reviewed scope.
