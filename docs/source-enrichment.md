# Settlement source enrichment

Live ingestion captures Kalshi event and series metadata, linked contract documents and publisher references, plus Polymarket market descriptions and embedded event context.
The implementation adapts the existing enrichment work to the landed `SourceRepository.record` interface and preserves the existing source migration.
It never replaces the original market rules with event descriptions.

The API exposes paginated provenance at `GET /api/v1/markets/{market_id}/sources` and original document bytes at `GET /api/v1/sources/{artifact_id}/content`.
Lists omit binary content and are isolated by live/simulation mode.
Downloads use an attachment response with `nosniff`, so external HTML is not executed under the application's origin.
The market's `raw.source_artifacts` stores immutable artifact identifiers and digests for audit reconstruction.

Retrieval permits only explicitly listed HTTPS hosts, forbids credentials, query strings and redirects, limits documents to `ARBBOT_SOURCE_MAX_BYTES` (default 1 MB), and bounds concurrent requests, retries, cache size and elapsed time.
Configure the byte limit below the absolute 5 MB storage ceiling.
Cache entries retain the original retrieval timestamp; using cached evidence does not claim a fresh source fetch.
JSON shape and PDF framing failures retain the received bytes plus a failed observation for diagnosis.
Unknown hosts and unsafe URLs are not fetched or echoed in failure messages.

Only semantic metadata and linked document digests enter settlement terms.
Changed event/series conditions or document bytes invalidate earlier definition hashes through the market terms hash.
Volatile volume and price fields remain in original artifacts and do not change settlement terms.
Missing or failed sources remain explicitly incomplete and prevent compatible settlement comparisons.
A documented shared event may still appear as an unverified comparison while its settlement evidence is incomplete.

Gamma metadata does not establish comprehensive post-publication clarification coverage.
Polymarket records therefore retain `supplemental_clarifications_unverified`; enrichment alone cannot authorize a live opportunity.
PDF capture is not semantic interpretation, and a successful download is not approval.
Broader publisher coverage and clarification review remain part of the matching and review workflow.

Official interfaces checked on September 24, 2026:

- [Kalshi event](https://docs.kalshi.com/api-reference/events/get-event)
- [Kalshi series](https://docs.kalshi.com/api-reference/market/get-series)
- [Polymarket market metadata](https://docs.polymarket.com/api-reference/markets/get-market-by-id)

The recorded Kalshi and Polymarket metadata fixtures preserve their capture provenance.
Linked document bodies in HTTP tests are explicitly synthetic and are not represented as recorded exchange rules.
Validation covers changed-source invalidation, volatile metadata, missing evidence, malformed JSON/PDF, allowlists, retries, size limits, cache reuse, persistence, API downloads and mode isolation on both SQLite and PostgreSQL.
