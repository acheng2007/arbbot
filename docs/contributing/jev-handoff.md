# Jev matching workflow handoff

## Status: October 14, 2026

Branch: `backend/completion`.
No PR or push was requested or performed.
Jev integration is implemented across persistent scheduling, immutable storage, matching, monitoring, APIs, generated contracts, browser comparisons, and the connected recorded acceptance harness.
Configuration and operational details are in [the classification guide](../jev-classification.md).

## Completed

The backend uses the direct OpenRouter Decisions API and pinned `typesafe/jev-1.13` model.
It defaults to two attempts per second, four concurrent requests, a durable 512-job queue, ten-second timeouts, and at most three transient attempts.
Provider backoff is shared, and configuration errors pause calls without stopping exchange polling.
Classification runs and current jobs/cursor use additive migration `b024_classification`.
Requests are bounded to 24 KiB and contain public metadata plus deterministic captured spans.
Evidence choices cannot manufacture quotations.
Semantic hashes exclude receipt-only updates, volatile JSON metadata, and fee captures.
Shared-document generations invalidate changed evidence without invalidating identical receipts from another market.
Only successfully applied runs can be reused from the 24-hour cache; late responses remain audit history.
CPU retrieval runs off the event loop.

Matching classifies retrieved pairs before the title cutoff and adds a bounded category/date supplement.
Both 0.80 probability and 0.80 confidence thresholds are required for additional candidates.
Explicit reference-period contradictions prevent additions.
Negative or uncertain advice never removes deterministic or previously reviewed pairs and never writes definitions or approvals.
Current API and monitoring reads suppress stale AI-only proposals.
Reviewed-pair retrieval now retains rejected/revoked pairs even without title overlap, while existing review eligibility remains authoritative.
API revalidation covers approvals and actual advisory results, then SQL applies ranking/filtering before pagination.
Monitoring avoids per-row job reads for ordinary title candidates.

Browser comparisons separate AI suggestions, established event evidence, and verified settlement.
They expose model scores, clause findings, captured quotations, coverage limitations, and lifecycle states.
Withdrawn AI-only pairs can still display their stale advisory result.
Snapshot-driven refresh includes classification queries.
Visual review also corrected hidden skip-link capture artifacts while retaining keyboard focus and improved quotation-caption wrapping.

The offline Decisions transport has no network fallback and schedules only declared recording pairs.
Acceptance decisions are explicitly scripted and excluded from accuracy metrics.
The authentic benchmark preserves 30 distinct Kalshi/US pairs and original source-backed terms.
Its baseline recall is eight of nine labeled counterparts.
All 30 include insufficient applicable exceptional-settlement evidence; these complete metadata records provide no uncertain event-identity gold cases.

## Verification

SQLite and PostgreSQL each passed 526 tests, including migration preservation and semantic invalidation.
The final focused classification/worker check passed 31 tests after moving retrieval off the event loop.
Frontend unit tests passed 65; fixture desktop/mobile browsers passed 56; connected desktop/mobile browsers passed six.
Type, lint, generated-contract, Ruff, whitespace, and webpack production-build checks passed.
Turbopack's production build could not bind its compilation port in this environment; the supported webpack build passed.
The acceptance harness now waits for actual fee-policy expiry after a fresh snapshot and tolerates legitimate optimistic revision conflicts.
Recorded book polling uses two seconds so SSE can observe freshly rechecked estimates reliably.

Connected artifacts are at `/tmp/arbbot-jev-final-acceptance/`.
Its `results.json` records candidate addition, source invalidation, explicit history, provider outage/recovery, uninterrupted books, worker restart, quote rechecks, review/access/fee gates, pagination, and browser delivery.
The benchmark report is [jev-benchmark.json](jev-benchmark.json).
The live smoke result is [jev-live-smoke.json](jev-live-smoke.json).
No OpenRouter key is configured, so live model responses, assisted recall, incorrect suggestions, and abstention metrics remain unmeasured.
No synthetic decisions are presented as observed model accuracy.

## Preserved local work

The pre-existing staged `docs/arbitrage-research-2026-09.md`, untracked `.specstory/`, and untracked `backend/arbbot/fees/kalshi.py` were left untouched and excluded from these commits.

## Next action

Configure `OPENROUTER_API_KEY` and run the documented 30-pair live benchmark to collect actual Jev responses before assessing assisted recall or model quality.
