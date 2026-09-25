# Durable review storage

`ReviewRepository` persists definition drafts and pair decisions as append-only revisions with mutable head pointers.
The repository is a storage foundation; authenticated HTTP mutations and worker consumption are not connected yet.
Existing file-based reviews continue to govern worker behavior until that integration is completed.

Each draft stores the complete market snapshot, canonical definition and hash, exact source artifact IDs, actor, timestamp and reason.
Each decision binds two immutable drafts and records its predecessor, action, reason and server-derived identity.
The actor is supplied by the trusted caller, never taken from an approval's reviewer string.
Approved payloads replace that string with a digest of the actor's issuer and subject.

Writers must provide the expected head revision, or null for initial creation.
Conflicting writes roll back the entire transaction and raise `RevisionConflict`.
PostgreSQL locks parent market rows in sorted order; SQLite acquires its write lock before reading a head.
Market and source writes participate in the same parent-row locking protocol on PostgreSQL.
Concurrent decisions cannot silently replace each other or leave orphan revisions.

Approval requires current drafts, matching terms and definition hashes, compatible contract definitions, valid evidence and an unexpired review.
Live approval additionally requires captured source evidence and referenced artifacts.
Changing a draft, market terms or a referenced source invalidates eligibility without deleting historical decisions.
Source retrieval failures also invalidate an approval when they supersede referenced evidence.
Evidence is tracked by exact artifact version, so even a non-semantic change to a referenced source can require renewed review.
Rejection and revocation retain the preceding approval for audit.
Mode isolation applies to revision lookup, history and eligibility.

Eligibility reads use a consistent database snapshot.
Workers must still revalidate immediately before publishing an executable opportunity; a previously returned eligibility result is not a permanent authorization.
Exceptional settlement scenario validation and authenticated API integration remain required before this storage can support the complete review workflow.

Migration `b016_review_revisions` adds four tables without rewriting existing markets, source artifacts or discovery catalogs.
Downgrading removes review history and heads, so it is destructive to review data.
Tests exercise concurrency, evidence invalidation, expiry, history reconstruction, mode isolation and preservation of preexisting data across migration upgrade and downgrade on SQLite and PostgreSQL.
