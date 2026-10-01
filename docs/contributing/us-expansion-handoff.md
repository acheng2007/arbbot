# US venue expansion handoff

## October 1, 2026 reroute

Branch: `backend/completion`.
The user canceled the Opinion/Limitless implementation and requested US-accessible markets with the same cross-market mispricing objective.
The [US venue expansion plan](../us-venue-expansion.md) and [roadmap](../implementation-roadmap.md) now supersede the earlier four-venue plan.

## Completed

Restored all 32 modified tracked implementation files to the pre-expansion HEAD, `31aa38a`.
Removed 17 newly created implementation paths covering the abandoned adapters, fixtures, registry, generalized event UI, fee integration, quote rechecks, and unfinished browser authentication/review editing.
Restored the original asynchronous interface of the pre-existing untracked Kalshi fee provider by removing only the added synchronous wrapper.
Preserved the user's staged research document, staged and unstaged research handoff, `.specstory/`, and pre-existing Kalshi provider.
Preserved and incorporated the user's US-focused roadmap edits.
No database reset, history rewrite, or running-container deployment was performed.
The abandoned implementation is recoverable locally from `/tmp/arbbot-abandoned-four-venue-20261001.tar.gz`; this temporary archive is not a durable project artifact.

Official documentation supports assessing Polymarket US, Crypto.com Predictions/CDNA, and ForecastEx/CME through IBKR.
The new plan separates exchange identity, broker route, public data access, and account/product eligibility.
It retains broad discovery and two-leg comparisons across every supported independent venue pair.
Polymarket International remains historical/research infrastructure and must not be silently relabeled as Polymarket US.

## Validation

After rollback, `.venv/bin/pytest -c backend/pyproject.toml backend/tests -q` passed all 417 tests.
`npm test --prefix apps/web` passed all 56 tests.
`git diff --check` passed before committing.
No new browser visual validation or live venue API smoke check was performed for this documentation-only reroute after restoring the original application code.

## Blockers and next action

Replacement venue endpoint behavior, catalog overlap, fees, source completeness, and user-specific eligibility remain unverified.
No replacement adapter, US eligibility gate, or seven-day paper study has been started.
The restored demo still contains International quotes and does not implement the planned US-only eligibility filter.
Do not describe its quotes as eligible US execution opportunities.

Single clearest next action: assess Polymarket US with immutable public catalog, rules, book, and fee fixtures; record access restrictions and actual overlap with Kalshi before implementing its adapter.
Continue with Crypto.com and then independently assessed ForecastEx/CME access, adjusting order only for documented blockers.
