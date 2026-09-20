# Backend authentication handoff

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
