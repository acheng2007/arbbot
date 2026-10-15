> Historical snapshot retained during the October 11, 2026 reconciliation.
> Branches, pending states, test counts, and next actions below describe earlier sessions.
> Use the [current handoff](../data-handoff.md) and [roadmap](../../implementation-roadmap.md) for active work.

# Data workstream handoff

## Completed

[D01 #2](https://github.com/acheng2007/arbbot/issues/2) persists immutable settlement source artifacts.
The contract is in `backend/arbbot/sources/models.py`, storage is in `backend/arbbot/sources/repository.py`, the table is registered as `SourceArtifactRecord` in `backend/arbbot/storage/models.py`, and the schema change is Alembic revision `d0cc5e73c848`.
Behavior is described in [docs/backend.md](../../backend.md) under "Settlement source evidence" and covered by `backend/tests/test_source_artifacts.py` on SQLite and PostgreSQL.

An artifact is content addressed, so an identical capture records another observation rather than a duplicate row, and a changed document creates a new artifact while the previous bytes stay readable.
    10|Failed retrievals are stored with the same provenance and an explicit reason, and oversized documents become `too_large` failures instead of truncated evidence.
Each artifact records the market terms hash that was current at capture time, so `missing_evidence` can treat evidence captured under superseded terms as unusable.

Nothing fetches evidence into this store yet, and no API route exposes it.

## Next action

Implement [D02 #3](https://github.com/acheng2007/arbbot/issues/3) and [D03 #4](https://github.com/acheng2007/arbbot/issues/4) to capture real Kalshi and Polymarket settlement evidence into the source store.
Both are now unblocked and use separate modules, so they can proceed in parallel.
Start with the two recorded Kalshi CPI markets in `backend/tests/fixtures/contracts/recorded.json`, whose market-level rules do not establish jurisdiction or the source publisher today.
    20|
## Notes for the next agent

Persist the market before its evidence; the repository rejects artifacts for an unknown market key and derives the terms hash from the stored market.
Use `bounded_capture` with `Settings.source_max_bytes` in fetchers so a large document is recorded as a failure rather than dropped.
Choose stable snake-case labels for evidence roles, such as `series_metadata` or `resolution_source`, because `missing_evidence` reports completeness per label.
Do not add mutation endpoints or review persistence here; those belong to [R01 #16](https://github.com/acheng2007/arbbot/issues/16) and [R03 #18](https://github.com/acheng2007/arbbot/issues/18).
Keep one additive Alembic revision per schema change and rebase its parent against current main before merge.
