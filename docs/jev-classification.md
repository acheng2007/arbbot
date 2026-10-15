# Advisory Jev classifications

Jev proposes event counterparts and compares clause meanings through OpenRouter's [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request).
The model is pinned to `typesafe/jev-1.13`.
Requests contain `model`, `state`, and typed `questions` directly, without chat messages or another generative model.
Python settlement comparisons, source applicability, automatic qualification, and financial gates retain authority.
Historical database approvals remain supported in the optional review-driven path; the default automatic workflow does not require them.
See the [system design](system-design.md) for the distinction between model advice, automatic qualification, and conditional estimates.
A model finding never writes a reviewed definition, approves equivalence, rejects an existing deterministic proposal, or places an order.
Confidence is a model score, not measured accuracy.

## Accepted visibility policy and current behavior

The [accepted candidate-visibility decision](decisions/candidate-visibility.md) supersedes score-based admission as the development direction.
Future behavior exposes every valid fresh `same_event` suggestion as Unverified, uses model scores for ranking, and derives Verified or Mismatch from automatic settlement checks.
Verification and positive financial opportunity publication remain separate.
The implementation described below still enforces both 0.80 candidate cutoffs; no settings or runtime behavior changed when this decision was documented.
Treat the threshold settings and initial benchmark as current/historical implementation evidence rather than requirements for future candidate visibility.

## Configuration

Set `OPENROUTER_API_KEY` in the backend environment or backend process's `.env` file.
Never put it in a `NEXT_PUBLIC_` variable or browser bundle.
Docker Compose passes the key only to backend processes.
Classification automatically runs in persistent live workers when the key is configured.
Simulation mode and missing credentials preserve deterministic matching.
Set `ARBBOT_CLASSIFICATION_ENABLED=false` to disable advice, including previously cached candidate contributions.
There is no daily spending cap.

| Setting | Default | Meaning |
| --- | --- | --- |
| `ARBBOT_CLASSIFICATION_REQUESTS_PER_SECOND` | `2` | Shared limit for all attempts, including retries; may be reduced, never raised above two |
| `ARBBOT_CLASSIFICATION_PROBABILITY` | `0.80` | Minimum same-event probability for an additional candidate |
| `ARBBOT_CLASSIFICATION_CONFIDENCE` | `0.80` | Minimum model confidence score for an additional candidate |
| `ARBBOT_CLASSIFICATION_RECORDING_FILE` | unset | Explicit offline Decisions response fixture; never falls back to network |

The worker supervises classification independently of catalog refresh, matching, fees, book polling, and evaluation.
It runs at most four requests concurrently and retains at most 512 pending/running jobs.
A durable cursor rotates remaining catalog work and survives restarts.
Interrupted running jobs return to the pending queue on restart.
Completion sets the existing coalesced catalog notification to wake matching.
No additional service or Redis is required.

## Retrieval and evidence

Existing structured-event, title-index, and reviewed-pair retrieval remains in place.
Classification evaluates retrieved pairs before the title similarity cutoff.
An additional category-normalized, nearby-close supplement contributes at most 20 new counterparts per endpoint, with limits disclosed.
Retrieval examines closing times within seven days, so distant exchange closing conventions can still prevent retrieval.
The supplement cannot guarantee full catalog recall.

Event choices are `same_event`, `different_event`, and `insufficient_evidence`.
Separate questions compare outcomes, resolution sources, cancellation, fallback, ambiguity, and revision clauses.
Clause choices are `same_meaning`, `different_meaning`, and `insufficient_evidence`.
Numerical thresholds, dates, rounding, payout semantics, and explicit reference-period contradictions remain Python decisions.
The current implementation only admits an otherwise excluded candidate when fresh same-event advice meets both configured thresholds; migrating this gate to the accepted visibility policy remains open.
Monitoring preserves verified, established-event, and watchlist priorities, then fresh AI-supported suggestions, other title suggestions, and unpaired markets.
Each priority tier rotates fairly.

Inputs contain public market metadata and deterministic captured text excerpts, with source IDs, exact text offsets, applicability, and coverage limitations.
Raw exchange payloads, account data, credentials, books, balances, and fees are excluded.
The serialized request is bounded to 24 KiB.
Relevant keyword windows and document/page limits bound excerpt selection; relevant omitted context remains a limitation.
Jev selects evidence IDs from supplied choices.
The application reconstructs quotations from captured spans and cannot accept model-invented quotations.
Missing clauses or unverified document applicability force insufficient evidence, even when a scripted or incorrect model answers confidently.
Market-specific primary terms are identified separately from documents requiring applicability approval.
Source text is explicitly treated as untrusted data rather than instructions.

## Storage and freshness

Migration `b024_classification` adds immutable classification runs, current job/run pointers, and durable scheduler state without modifying historical match payloads.
Runs retain supplied requests, semantic inputs and document generations, span references, model identity, question version, answers, probabilities, confidence, usage, timings, attempt counts, sanitized failures, and whether advice was applied.
Successful advice is cached for 24 hours by pair identity, semantic inputs, model, and question version.
Market terms, categories, document contents/generations/status, and applicability revisions/expiry affect that identity.
Quotes, fees, balances, and receipt-only updates do not.
Fee-policy captures and volatile exchange JSON metadata are excluded; their relevant settlement fields remain represented by normalized market terms.
Shared documents bind the market-specific artifact and shared content generation; another market's receipt of identical bytes does not invalidate advice.

Reads recheck input identity before exposing current advice.
Worker completion rechecks identity under market/document locks before updating the current result.
Late responses remain audit history and never become current advice.
Stale AI-only proposals disappear from current matching reads and monitoring unless deterministic evidence or a review independently retains the pair.
API filtering and ranking happen after revalidation and before pagination.
Read-scoped fingerprint memoization avoids repeated evidence queries for the same market within one catalog response.
Actual advisory results and approvals are revalidated before a SQL ranking/filtering projection paginates ordinary title suggestions.

## API and browser

`Match.classification` is optional for historical payload readability.
Current responses expose pending, fresh, stale, unavailable, unconfigured, and disabled states.
`GET /api/v1/matches/{match_id}/classification` returns current advice even after an AI-only proposal is withdrawn.
Add `?run_id=<id>` for explicit historical access; historical results are marked stale and never contribute to current suggestions.
`GET /api/v1/matches?classification=suggested` filters supported current advice before pagination.
The same filter accepts lifecycle states.
`GET /api/v1/status` reports sanitized provider health, queued work, last success, and provider errors separately from exchange health.
Comparison screens show AI suggestions separately from established event evidence and reviewed verification.
Clause details show selected captured quotations, model scores, source references, and applicability.
Existing snapshot-driven queries refresh advice and matching lists.

## Troubleshooting

Each provider request has a ten-second timeout.
Network failures, HTTP 408/429, and server failures receive at most three attempts with shared backoff and `Retry-After` support.
Malformed responses become unavailable advice instead of fabricated defaults.
Authentication, unsupported-model, or invalid-request responses pause provider calls until configuration is corrected and the worker restarted.
Exchange polling and deterministic matching continue.
Errors expose only fixed codes such as `provider_http_401`, `provider_http_503`, or `provider_invalid_response`.
Raw response bodies, request headers, and keys do not enter health or error messages.

## Verification commands

Run from the repository root unless a command explicitly changes directory.

```sh
cd backend
../.venv/bin/pytest -q
ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot ../.venv/bin/pytest -q
../.venv/bin/python -m arbbot.api.export_schema --output ../docs/openapi.json
../.venv/bin/python scripts/run_acceptance.py --classification --output /tmp/arbbot-jev-acceptance
../.venv/bin/python -m arbbot.matching.benchmark --output /tmp/jev-benchmark.json
../.venv/bin/python -m arbbot.matching.classification_smoke --limit 1 --output /tmp/jev-live-smoke.json
cd ../apps/web
npm run generate:api:check
npm run test
npm run typecheck
npm run lint
npm run build -- --webpack
npm run test:e2e
```

The connected acceptance harness uses PostgreSQL, the persistent worker, FastAPI, Next.js, and desktop/mobile browsers.
Its explicitly scripted offline Decisions responses exercise candidate addition, clauses, historical access, source invalidation, provider outage/recovery, pagination, and continuing book polling.
Offline scheduling only considers declared recorded pairs, so missing fixture coverage cannot silently invoke the live provider.
Scripted responses are not actual Jev predictions and are excluded from accuracy metrics.

The authentic benchmark retains 30 distinct Kalshi/US pairs with original October 1 public terms, capture provenance, source quotations, and proposition labels.
It contains nine same-event labels, 21 different-event labels, and 30 cases with insufficient applicable exceptional-settlement evidence.
The baseline retrieves eight of nine labeled counterparts using the current extraction/matching path.
These complete metadata records do not provide authentic uncertain event-identity gold cases; that portion of benchmark coverage remains a limitation.
The baseline is a small recorded sample, not a measured population accuracy estimate.
A live smoke check writes an explicit skipped result when credentials are absent.
## Initial live-provider results: October 15, 2026

A configured backend key successfully completed one smoke request and 30 benchmark requests against the pinned model; the provider returned `typesafe/jev-1.13-20260917` without errors.
The [sanitized benchmark record](contributing/jev-live-benchmark-2026-10-15.json) retains labels, input fingerprints, answers, model scores, returned model identity, and usage without credentials.
These are live model responses on the original recorded public market metadata, not live exchange discovery or scripted responses.

Raw event choices agreed with all 30 labels: nine same-event and 21 different-event cases.
None of the nine same-event answers met both 0.80 thresholds, so no candidate was added and assisted recall remained eight of nine, matching the deterministic baseline.
There were zero threshold-qualified incorrect suggestions and zero raw event abstentions.
This is one small, nonrepresentative sample without uncertain event-identity labels; it does not establish confidence calibration or population accuracy.

The benchmark reported 151,882 input tokens, 35,365 output tokens, and provider-reported cost of `0.006379044`; the separate smoke reported `0.000212604`.
These values are provider usage fields, not an independent billing audit or a production cost forecast.
Request-level latency was not instrumented by the harness.
All 30 pairs still lack sufficient applicable exceptional-settlement evidence.
The smoke harness loads recorded primary market metadata without supplementary captured document artifacts, so raw clause answers cannot establish clause accuracy or automatic qualification.
No thresholds or production behavior changed.
Next evaluation should add authentic uncertain/ambiguous identities and applicable clause evidence, measuring retrieval and ranking separately from verification under the accepted visibility policy.
