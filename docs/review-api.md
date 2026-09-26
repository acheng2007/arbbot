# Review API

Review routes require a verified bearer access token using the configured issuer, audience and JWKS endpoint.
Viewer permission is required for reads; reviewer permission is required for writes.
Browser mutation origins must match `ARBBOT_CORS_ORIGINS`.
Identity configuration and token validation are described in the [authentication documentation](authentication.md).

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/v1/markets/{market_id}/draft` | Current draft or null |
| GET | `/api/v1/markets/{market_id}/drafts` | Draft history, newest first |
| GET | `/api/v1/drafts/{revision_id}` | Exact immutable draft revision |
| POST | `/api/v1/markets/{market_id}/drafts` | Append a draft revision |
| GET | `/api/v1/reviews/current?left_id=...&right_id=...` | Current decision and current eligibility, or null |
| GET | `/api/v1/reviews/history?left_id=...&right_id=...` | Decision history, newest first |
| POST | `/api/v1/reviews` | Append an approval, rejection or revocation |

History endpoints accept `limit` from 1 to 100 and `offset` from 0 to 100000.
All routes use the server's configured data mode; clients cannot switch modes through query parameters or request bodies.
A market or revision absent from that mode returns 404.

Mutation bodies follow the generated OpenAPI `DraftWrite` and `DecisionWrite` schemas.
Send `expected_revision_id` with the head revision last read, or null when creating the first revision.
A successful write returns 201 and the new immutable revision.
The actor and timestamp come from the server; an actor field in the request is rejected.
The server overwrites the nested review's reviewer string with the authenticated principal's audit identity.

Concurrent edits and stale terms return 409 with `detail.code` equal to `revision_conflict`, a message, `current_revision_id` where available, and related evidence issues.
Reload the current revision and source evidence before retrying.
Invalid or incomplete review evidence returns 422 with `detail.code` equal to `invalid_review_evidence` and an issues array.
Malformed request bodies use FastAPI's standard 422 validation-error list.
Neither outcome writes a partial revision.

Live approval requires current source artifacts, current term and definition hashes, compatible definitions, explicit payouts and declared settlement-condition coverage.
Eligibility reads recheck expiry and changes to drafts, market terms or referenced source evidence.
Historical payloads remain available after invalidation or revocation.

With the default `ARBBOT_REVIEW_SOURCE=database`, live workers use current database drafts and approvals on each cycle.
An eligible approval permits evaluation; it does not imply that profitable executable quotes exist.
Revocations, new draft revisions and changed evidence immediately invalidate public opportunity reads, including before the next worker cycle.
Publication rechecks approval revision and eligibility while holding the same parent-market locks as review and evidence writes.
Every database-backed opportunity identifies its exact `review_revision_id`, and a replacement approval requires recalculation.
Current match reads also downgrade stale approvals before status filtering and pagination.
Historical opportunity reads retain the original review revision for audit.

Legacy file-based development requires explicit `ARBBOT_REVIEW_SOURCE=files` on both worker and API, with the corresponding file paths configured.
Database mode never falls back to files or exposes live opportunities lacking a database revision.
Simulation continues to use clearly labeled synthetic fixture reviews.
The real-pair corpus and joint exceptional-outcome validation remain incomplete; no human approval has been created by this implementation.
