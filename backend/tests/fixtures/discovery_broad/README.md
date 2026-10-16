# Authentic broad-discovery corpus

`recorded.json` preserves 31 public contract payloads with original URLs, capture times, response digests, and canonical payload hashes.
`metadata.json` preserves captured event/series response bytes for recorded source traversal and authentic Kalshi categories.
The corpus spans politics, economics, sports, and weather grouped as other.
A missing cross-venue economic offering is not filled with a fabricated contract.

`labels.json` contains source-reading event and outcome-orientation labels for 22 pairs.
These labels do not establish exceptional-settlement equivalence or general model accuracy.
Same-event political contracts can still have different YES conditions because media calls, officeholder affiliation, seats, and caucus definitions differ.

`jev-captured.json` preserves an actual v3 provider answer and an input-bound reconstructed request.
The original outbound bytes were not retained; the request was reconstructed with the same immutable payloads and question builder.
The replay rejects different request hashes and never falls back to a live provider.
Scripted low-score responses in tests and connected acceptance are separate visibility/failure cases.

Run `backend/scripts/benchmark_discovery.py` for retrieval and `--live` for actual provider calls using a configured backend key.
The October 15 result summary is under `docs/contributing/discovery-benchmark-2026-10-15.json`.
Both keyword and hybrid retrieval found all 11 labeled event counterparts in this small sample; this demonstrates no incremental embedding recall benefit.
