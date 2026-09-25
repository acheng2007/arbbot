# Targeted live discovery

The persistent live worker discovers a bounded catalog separately from its five-second quote loop.
Each venue has a background catalog task; initial catalogs must load before quotes are admitted.
Subsequent discovery and source enrichment run while the quote loop uses the previous immutable catalog snapshot.
An expired catalog suppresses its venue's opportunities, and cancellation waits for catalog work before closing the exchange clients.
Simulation continues to use explicit fixtures.

The default configured family is US CPI, using Kalshi series `KXCPI` and `KXCPIYOY` and Polymarket public searches for US inflation and CPI.
Configured families are candidate retrieval rules, not settlement definitions or approvals.
Market headings must contain a configured family keyword; incidental mentions in descriptions or publisher citations do not qualify unrelated contracts.
The complete original rules still govern semantic comparison.

Configuration:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ARBBOT_DISCOVERY_FAMILIES` | US CPI | JSON array of `name`, `kalshi_series`, `polymarket_queries` and `keywords` |
| `ARBBOT_DISCOVERY_LIMIT` | 50 | Maximum selected markets per venue |
| `ARBBOT_DISCOVERY_SCAN_PAGES` | 8 | Maximum family-search pages per refresh |
| `ARBBOT_CATALOG_REFRESH_SECONDS` | 300 | Delay between completed refresh attempts |
| `ARBBOT_CATALOG_MAX_AGE_SECONDS` | 900 | Maximum age measured from the start of a successful refresh |
| `ARBBOT_CATALOG_TIMEOUT_SECONDS` | 120 | Deadline for discovery and enrichment |

The maximum catalog age must exceed refresh delay plus refresh timeout.
Explicit `ARBBOT_KALSHI_TICKERS` and `ARBBOT_POLYMARKET_MARKET_IDS` override family search for that venue and retain eligibility checks.
Set the family JSON in the Compose environment file or process environment to use another configuration.
HTTP reads are paced and retried by the exchange adapter.
Page scans stop on exhausted or repeated cursors, page budgets, catalog limits, or the 2,000-decision cap.
Search terms share the market budget so the first series cannot fill every slot.
This is bounded monitored coverage, not a claim of exhaustive exchange discovery.

`GET /api/v1/discovery` returns the latest durable report for each venue in the API's mode.
Reports name selected contracts, inclusion/exclusion reasons, source-evidence gaps, scan counts, truncation, refresh errors, and expiration.
Failed refreshes retain an earlier successful catalog only until its original deadline; a failed request never renews that deadline.
On restart, the worker rebuilds catalogs before admitting quotes rather than treating persisted reports as current exchange state.
The additive `b005_discovery_catalogs` migration preserves the existing source and market histories.

The September 24 recorded CPI discovery sample contains supported Kalshi contracts but excluded negative-risk Polymarket inflation buckets.
This accurately explains the lack of supported counterparts in that sample.
The scanner does not alter negative-risk eligibility, infer equivalence, or generate human approvals to manufacture a pair.
Other families, broader extraction and supported positive pair validation remain necessary for the complete backend.

Official request contracts were checked against [Kalshi market filters](https://docs.kalshi.com/api-reference/market/get-markets) and the [Polymarket Gamma OpenAPI schema](https://docs.polymarket.com/api-spec/gamma-openapi.yaml).
Recorded fixtures preserve the capture URL, time, original response digest and explicit projection note.
Tests exercise recorded replay, pagination, duplicate suppression, watchlist precedence, unrelated categories, unsupported contracts, budget exhaustion, catalog expiry, shutdown, mode isolation, and quote updates during a stalled catalog request.
