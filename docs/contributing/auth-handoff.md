# Backend authentication handoff

## Latest main reconciliation

The user authorized reviewing and merging passing foundation PRs #44 and #46 through #51.
PRs #44 and #47 have landed; this branch now integrates main `f91a639a809db8c6562b1793028aa693d7e97f3f`.
All 234 SQLite tests and Ruff lint/format checks passed with the newly landed canonical definitions and catalog filtering.
Authentication and tracing API conflicts were resolved additively in their respective branches, and authentication's OpenAPI was regenerated from code.
Docker Desktop is manually paused, so no new local PostgreSQL result is claimed for this reconciliation.
Earlier database results remain recorded below; the new head requires hosted PostgreSQL, migration and schema checks.
Next action: verify the new hosted run, then perform the authorized merge without duplicating externally completed merges.
The backend production goal remains incomplete; durable reviews, venue policies and streams, and production validation follow the foundation merges.

## Current integration and review update, 2026-09-21

Integrated main at `98f2791632389523cbf93bfb591e69267fd82b3e`, including landed source storage and the negative-risk assessment.
Reproduced a slow JWKS response through the API: continuously arriving chunks kept concurrent authentication calls waiting beyond the intended timeout.
Added a five-second total retrieval deadline alongside HTTPX timeouts; timeout becomes 503, closes the response, releases the refresh lock, and permits later recovery after cooldown.
The regression exercises concurrent callers and successful authentication after the provider recovers.
All 141 tests passed on SQLite and isolated PostgreSQL 17; all 34 focused authentication tests passed.
Ruff lint/format passed.
Also applied the already reproduced shared future-quote test correction from PRs #44/#47, keeping quote timestamps relative to one explicit evaluation instant.
This changes test determinism only, not quote eligibility behavior.
Hosted CI must verify this updated commit before merge.

Canonical PR #44's latest handoff commit `6b708bef3fe2bc5a86f18a6c8a8b176ee23f9778` passed hosted run 35561251633.
PRs #44 and #47 are ready for review; merge authorization for foundation PRs #44 and #46 through #51 remains pending.
PR #45 is excluded because source storage already landed through a separate implementation.
Next action: verify this auth PR's latest hosted run, then finish reviewing/merging authorized prerequisites and implement durable review storage #16 once #44 lands.

## Historical implementation record

The current update above supersedes earlier base, test-count and next-step details below.

The complete backend production goal remains active.
This increment implements issue #17 only; review persistence/mutations and real provider deployment remain unfinished.
Workspace: `/private/tmp/arbbot-backend-auth`.
Branch: `backend/17-reviewer-auth`, from `origin/main` at `d065906`.
Published draft PR: https://github.com/acheng2007/arbbot/pull/48.

## Completed

Implemented an OAuth resource server using RFC 9068 RS256 access tokens and pinned PyJWT 2.14.0.
The trusted issuer, dedicated API audience, HTTPS JWKS URL, token lifetime, and key cache bounds are configuration.
Viewer/reviewer permissions derive only from verified issuer-granted scopes.
Audit identity derives from verified issuer and subject, with no request-supplied reviewer override.
Added reusable FastAPI dependencies and the protected `/api/v1/auth/me` endpoint.
Protected mutations using the reviewer dependency reject untrusted/null origins and cookie-only credentials.
JWKS fetching is asynchronous, bounded, cached, refresh-throttled, and fail-closed after expiry; tokens cannot supply key URLs.
Existing public reads remain available with authentication unconfigured, but protected verification returns unavailable.
No password storage, token issuance, review mutation, or frontend login implementation was added.
Read `docs/authentication.md` for provider requirements, local development, CORS/CSRF, key rotation, and deployment limitations.

The dependency manifests/locks and generated OpenAPI were updated as necessary integration edits alongside Settings and application registration.
Primary sources consulted were PyJWT's official API documentation and RFC 9068; links are in the authentication document.

## Validation

Full backend suite: 108 passed independently on SQLite and PostgreSQL.
Coverage includes signed requests through the FastAPI dependency chain, viewer/reviewer separation, server-derived identity, expired/missing/invalid claims, algorithm/signature errors, duplicate Authorization headers, cookie rejection, browser preflights/origins, malformed or oversized JWKS, cache refresh/rotation, and outage recovery.
No live provider was contacted; tests use ephemeral RSA keys and mocked JWKS HTTP.
An intentionally invalid HMAC fixture initially emitted a short-key warning; its key was lengthened while retaining the algorithm-confusion rejection test.
All 33 focused authentication tests then passed without warnings.
Ruff lint/format and OpenAPI regeneration passed.
Hosted CI for this new branch and actual tenant configuration are not yet verified.

## Other backend branches

- PR #44: definitions, `/private/tmp/arbbot-backend-contracts`, hosted CI passed at `b3a0fff`.
- PR #45: source evidence, `/private/tmp/arbbot-backend-production`, hosted CI passed at `fa24676`.
- PR #46: fee contracts, `/private/tmp/arbbot-backend-fees`, mixed-case asset fix at `ca90c78` passed hosted run 35523215490.
- PR #47: catalog filtering, `/private/tmp/arbbot-backend-catalog`, hosted run 35538406140 passed at `daff220`.

All remain separate reviewable draft PRs; no unreviewed branch has been merged.
Source and catalog migrations currently share a parent; rebase the second migration onto the first reviewed/merged revision and test the combined graph before merging.
The original frontend workspace still contains its unrelated user changes.

## Remaining production scope and next step

Source enrichment/discovery/corpus, expanded extraction, exceptional settlements, venue fees/slippage, persistent reviews and review APIs, streams/recovery/revalidation, observability, staging, backup/recovery, and combined end-to-end validation remain.
The user was asked asynchronously which production host and identity provider to use, with non-secret issuer/audience details; no answer has arrived yet.
Continue independent implementation while that deployment choice is pending.
Do not mark production readiness from fixture tests or from isolated PRs.

Next action: verify PR #48 hosted CI, then implement dependency-free stream/resynchronization contracts (#27) on a new branch from current main.
Use `docs/contributing/README.md` for dependencies and keep one issue per PR.
