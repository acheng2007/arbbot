# Hosted backend CI

The repository runs `.github/workflows/backend.yml` for pull requests, pushes to `main`, and manual dispatch.
The workflow is named `Backend checks`; its check job is `backend`.
It uses Python 3.14 and a PostgreSQL 17 service, installs the committed development lockfile, then installs the backend without resolving additional dependencies.
It does not contact live exchanges or require exchange credentials.

## Verified hosted evidence

On 2026-09-20, [run 35539470739](https://github.com/acheng2007/arbbot/actions/runs/35539470739) completed successfully for stream PR [#49](https://github.com/acheng2007/arbbot/pull/49), head commit `0232aefe54c3346bab9a6742a3d7be3545698415`.
The [backend job and step output](https://github.com/acheng2007/arbbot/actions/runs/35539470739/job/106154402965) were inspected, rather than inferring success from a local run or the workflow file.
This demonstrates the hosted backend foundation with that PR's stream tests, not a production deployment or completion of later features.

| Gate | Observed hosted result |
| --- | --- |
| Pinned dependency installation | Completed successfully on the hosted runner. |
| Ruff lint and formatting | All checks passed; 44 files already formatted. |
| SQLite tests | 89 passed. |
| PostgreSQL tests | 89 passed against PostgreSQL 17. |
| Migration and model drift | Upgrade completed; Alembic reported no new upgrade operations. |
| Recorded contract report | Completed: 9 markets, 3 supported by adapters, 63 labeled fields, 14 correct fields, 0 incorrect fields. |
| Published API contracts | OpenAPI, review schema, and definition schema regenerated; the committed files had no diff. |

The recorded report exposes incomplete extraction coverage; a successful report command is not evidence that all fields or real cross-exchange pairs are supported.
The current suite and corpus must grow with the remaining implementation issues.

Earlier source-artifact and canonical-definition PR checks exposed backend test helper imports that were not portable to the hosted installation.
Those branches added `backend/tests/__init__.py` so their cross-test imports resolve consistently, without removing assertions or lowering coverage.
The source-branch correction is commit `fa24676` on PR [#45](https://github.com/acheng2007/arbbot/pull/45).
This documentation PR does not copy branch-specific test changes into `main` or alter the already passing workflow.

## Maintainer setup for required checks

Repository protection settings are intentionally unchanged by this work.
A maintainer can configure a rule targeting `main` through repository Settings, using either the repository's existing ruleset or branch-protection mechanism.

1. Require pull requests and the desired review policy before merge.
2. Enable required status checks and select the actual `backend` check emitted by GitHub Actions, not just the `Backend checks` workflow title.
3. Where offered, restrict that check's expected source to GitHub Actions.
4. Choose whether branches must be up to date before merging, then verify the latest proposed head or merge commit has completed the required check.
5. Confirm a failing required check prevents merging and that the normal reviewed, passing workflow remains usable.

Keep the job name unique across workflows to avoid ambiguous checks.
GitHub requires a check to have succeeded in the repository within the past seven days before it can be selected as a required status check.
If it is absent from the selector, inspect Actions and rerun the existing workflow before changing its name or weakening protection.
See GitHub's [protected branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) and [required-check troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

## Investigating failures

Open the failing run, confirm the tested commit and trigger, and inspect the first failing step and its logs.
Use the same lockfile and Python version when reproducing dependency or import failures locally.
For database failures, run the PostgreSQL suite and migration checks against an isolated development database.
For schema drift, regenerate from the backend models and review the diff; do not edit generated schema JSON by hand.
Preserve assertions and required gates while fixing the cause.
Do not treat an older successful run, a skipped job, or local tests as proof that a newer commit passed hosted CI.

Frontend CI and full browser review-to-opportunity tests belong to issue #33.
Staging deployment, a real collector and identity provider, and recovery rehearsal remain separate production requirements.
