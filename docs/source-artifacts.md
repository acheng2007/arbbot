# Settlement source artifacts

Issue #2 adds storage for evidence that future Kalshi and Polymarket source fetchers will collect.
Apply migrations using the existing backend setup instructions before using `SourceRepository`.
This change does not fetch documents or change matching, approval, or opportunity behavior.

## Capture contract

`arbbot.sources.models.SourceCapture` contains the simulation/live mode, persisted market ID, venue, HTTP(S) source URL, timezone-aware retrieval time, and explicit success/failure status.
A successful capture requires nonempty original bytes and a content type, with no error.
Its SHA-256 digest is calculated from the original bytes, including binary documents.
A failure requires an error description and cannot carry content or a content type.
A capture is evidence of retrieval, not proof that settlement evidence is complete or that contracts are equivalent.

Content is limited to 2 MiB per capture.
URLs, content types, market identifiers, and errors also have length limits.
URLs with embedded username/password credentials are rejected.
Fetchers must remove secret query parameters and sanitize error descriptions before persistence.
Future fetchers must enforce the content limit while streaming the response, then save a failure such as `response_too_large` instead of truncated content.
Model validation rejects oversized captures; it does not automatically persist retrieval failures.

## Storage semantics

`SourceRepository.save(capture)` validates the input again, verifies its market/mode/venue association, and inserts without updating existing rows.
Identical successful captures for the same market, mode, venue, URL, content bytes and content type share an ID and retain the first stored retrieval time.
Concurrent duplicate inserts use database conflict handling.
Changed content or content type creates a new version without overwriting earlier evidence.
Different URLs, markets, and modes do not share capture identities.
Failures include their retrieval timestamp in the identity, so retrying the same failure is idempotent while later failed attempts remain separate records.

`SourceRepository.history(mode, market_id, limit=100, offset=0)` returns captures newest first, with deterministic ID ordering for tied timestamps.
Consumers must inspect status; a recent failure must not be represented as successful fresh evidence.
There is no mutable latest-evidence pointer or automatic approval update.
The repository exposes no update/delete operation; it does not prevent privileged direct SQL changes.

## Migration and verification

Migration `b73c12904a61` adds `source_artifacts`, a market foreign key and a history index.
Original bytes use binary storage and capture metadata uses PostgreSQL JSONB, with SQLite compatibility for tests.
Downgrading removes source capture history but preserves pre-existing market tables.

Run `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_source_artifacts.py` from the repository root.
The tests cover version preservation, concurrent duplicate writes, binary round trips, failures, validation, association isolation, pagination, and SQLite migration upgrade/downgrade/schema checks.
Set `ARBBOT_TEST_DATABASE_URL` as documented in README to run repository tests in isolated PostgreSQL schemas.
PostgreSQL repository and migration validation still needs an available PostgreSQL service.
