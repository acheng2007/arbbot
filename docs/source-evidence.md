# Source evidence storage

`SourceRepository` stores settlement documents independently of market metadata snapshots.
Each artifact binds exact bytes, SHA-256 digest, media type, source URL, venue, and market including simulation/live mode.
The repository requires that the associated market already exists at that venue.
Retrieval captures separately record retrieval time, HTTP status, and success or a bounded failure code.
Unchanged content reuses its artifact; distinct retrieval times remain auditable.
Retrying the same capture, including concurrent retries, is idempotent.
Changed source bytes create a new artifact without altering the old one.

Documents are limited to 2 MiB and successful captures must contain nonempty content.
Fetchers must enforce this limit while streaming, then record `too_large` with no content when exceeded.
Other failures are `timeout`, `http_error`, `network_error`, and `invalid_content`.
Partial bodies are never accepted as successful evidence.
URLs must be public evidence URLs without embedded credentials, queries, or fragments.
Retrieval failures do not automatically invalidate prior artifacts, nor does successful retrieval establish semantic completeness or equivalent settlement.
Consumers must explicitly evaluate freshness, source coverage, and matching evidence.

Apply Alembic migrations before use.
Database triggers reject updates and deletes of artifacts and capture history in both PostgreSQL and SQLite.
The application repository exposes append and paginated history operations only.
Production application roles must not own tables or have DDL or TRUNCATE privileges; database administrators can still remove evidence and must be governed operationally.
Downgrading this migration explicitly removes the evidence tables and their contents.

Exchange fetchers, API endpoints, parser integration, and review linkage remain separate work.
This storage layer alone does not ingest evidence from live exchanges.
