# Automatic qualification handoff

## Status: October 15, 2026

Branch: `backend/completion`.
The automatic backend/API workflow is implemented.
The user authorized direct publication to `origin/backend/completion` on October 15, 2026.
The dashboard's separate potential-opportunity workflow remains deferred at the user's request.

## Completed

Live matching defaults to automatic settlement qualification without human review records, imported applicability approvals, or an account profile.
Versioned evidence providers and family rules supply immutable normalized definitions, payout models, source references, and assessment history.
Jev remains advisory; even maximum model confidence cannot supply qualification.
Unknown language and missing evidence produce explicit incomplete states.
The engine enumerates independent exceptional outcomes and retains worst-case financial, liquidity, fee, freshness, and transaction guards.
Public fee refresh no longer depends on installation access approval.
Account access, balances, borrowing, fee class, and known restrictions are exposed as assumptions rather than fabricated verified permissions.

A durable 512-pair coalesced queue, four supervised qualification tasks, restart recovery, leases, expiry renewal, and fair cursor rotation integrate with the persistent worker.
Semantic caching excludes quotes, fee captures, and unchanged receipts.
Source generations, terms, policy/provider versions, and explicit vetoes invalidate assessments.
Late responses remain audit history.
Publication checks the exact current assessment and settlement model within the transaction.

Potential price gaps have separate persistence and APIs.
Unknown costs remain null; incompatible currencies cannot be summed into a gap.
Qualification filters and current eligibility checks precede pagination.
New assessment/history APIs, operational health, and SSE payloads are generated into OpenAPI and TypeScript.
Migration `b025_qualification` preserves historical review and opportunity payloads.
Optional authenticated `cleared` decisions remove an operator veto without a human approval payload.

Venue identities, evidence capabilities, fee refresh, source-host registration, fee formula registration, and normalized execution semantics support additional platforms without evaluator venue branches.
A test-only fourth venue exercises the full qualification/calculation/publication/read/invalidation path.
Existing frontend compatibility changes are limited to nullable-review handling and badges that accurately distinguish automatic qualification from human review.
No potential-opportunity dashboard or qualification inspection interface was added.

## Production coverage boundary

Complete interpretation currently uses a closed explicit product-description grammar plus existing family identity extractors.
This does not establish arbitrary natural-language contract equivalence.
All 30 authentic benchmark pairs retain incomplete settlement interpretations or missing applicable exceptional evidence.
The recorded positive acceptance examples are explicitly synthetic complete contracts and synthetic instrument/document bindings, with captured public fee documents.
They verify automation and financial gates, not authentic settlement compatibility or model accuracy.
Authentic recordings remain unchanged and cannot use synthetic applicability bindings.
No OpenRouter key is configured, so no live Jev measurement is claimed.

## Verification

The full SQLite and PostgreSQL suites each passed 566 tests.
Final source-contradiction and bounded streaming-pagination checks also passed separately on both databases after full-suite collection.
The final focused financial/gating check passed 18 tests.
The automatic PostgreSQL worker/API harness passed all checks without human records or account setup.
Desktop/mobile fixture compatibility passed all 66 tests in the final serial run.
The report is [automatic-qualification-acceptance-2026-10-14.json](automatic-qualification-acceptance-2026-10-14.json).
Persistent acceptance artifacts are at `/tmp/arbbot-auto-final/`, with full-suite logs at `/tmp/arbbot-auto-sqlite-release.log` and `/tmp/arbbot-auto-postgres-release.log`.
Frontend units passed 66 tests.
Type, lint, generated-client, Ruff, whitespace, and webpack production-build checks passed.
The warm latency checks measure stored-book potential publication and assessment-completion-to-publication within two seconds for the declared synthetic pair.
An initial test incorrectly included cold discovery and qualification in that target; the final assertion measures the planned warm boundary.
Overlapping validation processes exceeded the harness cold-start deadline, so the final persistent acceptance ran without competing backend suites.
Two initial browser failures passed isolated reruns and the final complete serial suite; their screenshots showed loading/hydration state rather than a persistent layout regression.
Recorded source setup now waits for bounded provider recovery before tests assert unrelated financial behavior.

Operational configuration, API contracts, supported language, extension interfaces, and reproducible commands are in [automatic qualification](../automatic-qualification.md).

## Preserved local work

The pre-existing staged `docs/arbitrage-research-2026-09.md` and untracked `.specstory/`, `.playwright-mcp/`, and `backend/arbbot/fees/kalshi.py` remain untouched and excluded from this implementation.

## Next action

Extend the versioned production applicability and source-language providers using captured authentic specifications and amendment inventories, then measure how many of the existing authentic benchmark pairs can qualify without per-pair review.
