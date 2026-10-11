# US venue expansion handoff

## Current status: October 11, 2026

Branch: `backend/completion`; no PR was opened or remote status rechecked during this cleanup.
This update reconciles the local implementation and documented delivery evidence.
See the [roadmap](../implementation-roadmap.md) for the integrated sequence and the [project status handoff](project-status-handoff.md) for the October 11 checks and limitations.
Prior session details and validation evidence are preserved in [history](history/us-expansion-handoff.md).

## Completed baseline and local progress

The October 1 reroute deferred Opinion/Limitless and preserved the original Kalshi/Polymarket International history.
Polymarket International remains a separate research identity, not a US trading route.
Local uncommitted work now includes immutable Polymarket US catalog/book/fee/restriction recordings, a separate adapter, venue registration/API metadata, configured catalog filtering, and venue-aware browser panels.
Rule-backed World Series extraction identifies a recorded Kalshi/Polymarket US Dodgers candidate while retaining incomplete settlement status.
Automated tests explicitly reject malformed books and suppress US evaluation.
The older statement that no US adapter or recordings exist is superseded.

## Blockers and acceptance

Complete rulebook/clarification evidence, applicable fees, and account/product eligibility remain unverified; Polymarket US evaluation is deliberately blocked.
The local registry is not a complete capability/eligibility model.
Fresh worker/API/PostgreSQL and desktop/mobile validation is blocked by the unavailable Docker daemon.
Crypto.com and ForecastEx/CME capability assessments and the seven-day study remain unfinished.

## Next action

Finish the existing US discovery milestone before adding another venue.
Restore Docker and run `node scripts/smoke-us-demo.mjs` from `apps/web` against the configured demo stack, inspect desktop/mobile output, and verify fresh quotes plus retained candidate/incomplete labels.
Run appropriate PostgreSQL/migration checks and document the capability matrix, unsupported instruments, and outstanding rules/fees/access evidence.
Commit the focused implementation only after these checks; retain evaluation blocking until evidence and human review support it.
