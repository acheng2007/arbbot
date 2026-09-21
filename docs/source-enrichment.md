# Source enrichment review, issues #3 and #4

This draft integrates the uncommitted source-storage and definition-vocabulary foundations in a separate checkout.
It adds venue-specific evidence collection to live ingestion before book reads and matching.
Simulation is unchanged.

## Kalshi

The collector follows a market's explicit event ticker to the event API, then the event's explicit series ticker to the series API.
It preserves event group flags, series settlement sources, original contract references, current contract references, and additional prohibitions.
Linked documents are captured only from the fixed allowlist.
Missing fields and failed requests remain explicit; ticker spelling is never used to infer jurisdiction or publisher.
Capturing group flags does not implement complete group settlement scenarios or admit Polymarket negative-risk contracts.

Official references: [Get Event](https://docs.kalshi.com/api-reference/events/get-event) and [Get Series](https://docs.kalshi.com/api-reference/market/get-series).
Recorded CPI event and series responses are in `backend/tests/fixtures/kalshi_sources/`, with URL, save timestamp, and SHA-256 provenance.

## Polymarket

The collector records the Gamma market response, original description, resolution-source reference and returned event descriptions as supplemental context.
Event context does not replace market rules or prove contract equivalence.
The collector marks metadata changes during capture and follows only allowlisted resolution-source URLs.
Unverified supplemental clarifications remain an explicit incompleteness reason; this implementation does not claim comprehensive post-publication clarification coverage.
No unsupported clarification field or endpoint is invented.
Negative-risk eligibility is unchanged.

Official reference: [Get market by ID](https://docs.polymarket.com/api-reference/markets/get-market-by-id).
A recorded public response is in `backend/tests/fixtures/polymarket_sources/`, with provenance.
Tests use explicitly synthetic linked-document bodies and failures, not fabricated live recordings.

## Retrieval and persistence

The shared source reader allows exact HTTPS hosts for the two public metadata APIs, Kalshi contract assets and BLS.
It rejects other hosts, credentials, query strings, fragments, nonstandard ports and all redirects.
Requests use a dedicated unauthenticated client with environment proxies disabled.
This deliberately leaves unsupported source URLs incomplete instead of attempting general web scraping.

Each response is limited to 2 MiB and approved JSON/PDF/plain-text/HTML types.
Reads allow at most three attempts, a five-second per-request timeout and a 20-second overall read budget.
An enrichment hook has a 30-second per-market budget; timeout marks that market's evidence incomplete while allowing book ingestion to continue.
Successful responses are cached for five minutes with a 128-entry cap; failed reads are not cached.
At most eight listed sources or events plus the two Kalshi contract references are examined.

Original metadata/document bytes and retrieval failures are persisted through `SourceRepository`.
Raw market metadata lists artifact URLs and digests for audit.
Only semantic metadata, external-document digests and stable issue codes participate in settlement terms, avoiding review churn from volume or retrieval timestamps.
Fresh failures do not silently reuse expired cached success.
Source changes alter the market terms hash and invalidate earlier definitions/reviews.
Incomplete evidence blocks compatible structured comparison even if a definition otherwise fills the required fields.
A `captured` status means retrieval succeeded; it never means semantic equivalence was approved.

## Integration boundaries and limits

Shared edits beyond venue modules are the source reader, the pipeline's enrichment hook and the comparison incompleteness gate.
The existing market API exposes enriched settlement details and audit references without a new endpoint.
No database migration beyond issue #2 is added.
Source artifacts currently have repository-level history access; there is no new public artifact-download route.

This draft retains synchronous bounded enrichment in the existing discovery cycle.
At large watchlist sizes the per-market budget can still extend a cycle; issue #5's independent catalog scheduling must address that before increasing scan limits.
The Kalshi group-evidence gap is only partially addressed: flags are captured, but complete sibling/group review remains separate work.
Polymarket clarification coverage and nonallowlisted external sources remain explicit limits.
PostgreSQL execution, hosted CI and live end-to-end operation have not been verified in this environment.
