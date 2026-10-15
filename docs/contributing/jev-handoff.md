# Jev matching workflow handoff

## Status: October 15, 2026

Branch: `backend/completion`.
Publication requested to `origin/backend/completion` on October 14, 2026.
No PR was requested.
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
The original October 14 validation had no configured key; its skipped live-smoke artifact is historical.
The October 15 live run below supersedes that measurement limitation for this recorded sample.
No synthetic decisions are presented as observed model accuracy.

## October 15 live-provider measurement

The user configured the ignored root `.env`; the key was loaded through backend Settings without printing it or adding it to Git.
One smoke and all 30 benchmark requests succeeded with no provider errors.
Requested model: `typesafe/jev-1.13`; returned model: `typesafe/jev-1.13-20260917`; question set: `counterparts-v1`.
All raw event choices match the existing labels: nine same-event and 21 different-event cases.
None of the same-event answers passes both configured 0.80 thresholds, so the run adds zero candidates and assisted recall remains eight of nine.
There are zero raw event abstentions and zero threshold-qualified incorrect suggestions.
Do not describe raw agreement on this small easy-label sample as general accuracy, calibrated confidence, or retrieval improvement.

The [live benchmark record](jev-live-benchmark-2026-10-15.json) stores sanitized actual answers, input hashes, labels, model identity, usage, and limitations.
The 30-pair benchmark reports cost `0.006379044`; the separate smoke reports `0.000212604`, as returned by the provider.
Billing and per-request latency were not independently measured.
Full local requests/responses are at `/var/folders/1_/9zkc7n756s350ydj5w3y_tkw0000gn/T/arbbot-jev-live-azebu8s7/`.
The metadata-only harness does not load supplementary source artifacts; raw clause answers are not a settlement-quality evaluation, and all 30 authentic pairs remain incomplete.
Thresholds and application code were unchanged, and no persistent live worker was started.
The benchmark was recomputed from actual outputs and checked against per-pair threshold/period guards; documentation links, whitespace, and credential exclusion were checked before commit.
The README, classification guide, roadmap, and integrated handoff now distinguish this measurement from prior scripted acceptance and unmeasured production behavior.

## Preserved local work

The pre-existing staged `docs/arbitrage-research-2026-09.md`, untracked `.specstory/`, and untracked `backend/arbbot/fees/kalshi.py` were left untouched and excluded from these commits.
Additional browser-debug artifacts under `.playwright-mcp/` were also excluded.

## Next action

Expand the authentic evaluation with uncertain/ambiguous event identities and applicable clause evidence, then assess held-out candidate-threshold calibration without weakening deterministic contradictions or settlement qualification.
