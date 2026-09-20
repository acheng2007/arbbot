# Authentication and reviewer authorization

Arbbot acts as an OAuth resource server for an external identity provider issuing [RFC 9068 JWT access tokens](https://www.rfc-editor.org/rfc/rfc9068.html).
Signature and registered-claim verification use pinned [PyJWT 2.14.0](https://pyjwt.readthedocs.io/en/latest/api.html) with the existing cryptography dependency.
Arbbot does not store passwords, issue login tokens, or accept OpenID Connect ID tokens as API credentials.
Provider/tenant deployment remains an operational integration step.

## Provider configuration

Configure these settings together on the API process, including local development:

```text
ARBBOT_AUTH_ISSUER=https://your-identity-provider.example/issuer/
ARBBOT_AUTH_AUDIENCE=arbbot-api
ARBBOT_AUTH_JWKS_URL=https://your-identity-provider.example/issuer/jwks
ARBBOT_CORS_ORIGINS=["http://localhost:3000"]
```

Use the provider's exact issuer string and published JWKS endpoint; verify them through trusted provider metadata.
Identity URLs require HTTPS without embedded credentials, query strings, or fragments.
The API never follows signing-key URLs supplied by a token and does not follow JWKS redirects.
Use a dedicated API audience distinct from the frontend OAuth client ID.
Configure the provider to issue RS256 access tokens with a `typ` header of `at+jwt` or `application/at+jwt`, a signing-key `kid`, and `iss`, `sub`, `aud`, `exp`, `iat`, `client_id`, and `jti` claims.
The optional `nbf` claim is enforced when present.
The issuer controls granted scopes; the application must not let clients self-assign reviewer scopes.
Arbbot recognizes `arbbot:read` as viewer access and `arbbot:review` as reviewer plus viewer access.
Other roles/claims/request headers do not grant permissions.

Defaults allow tokens lasting at most 900 seconds, with no clock-skew allowance.
`ARBBOT_AUTH_MAX_TOKEN_SECONDS` supports 60 to 3600 seconds and `ARBBOT_AUTH_CLOCK_SKEW_SECONDS` supports 0 to 30 seconds.
Keep API and provider clocks synchronized.
Changing or revoking an identity-provider role takes effect when a new token is issued or the old token expires; there is no token introspection or immediate per-token revocation in this implementation.
Require suitable provider-side MFA and grant restrictions for reviewers in production.

## API integration and audit identity

Call `GET /api/v1/auth/me` with `Authorization: Bearer <access-token>` to retrieve the verified principal.
The response contains issuer, subject, client ID, roles, and a deterministic audit ID derived from issuer and subject.
Mutation handlers must use the `require_reviewer` dependency and take their audit identity from the returned principal.
Never accept a reviewer ID from request JSON or a user-supplied identity header.
The `require_viewer` dependency is available for protected read routes.
Existing market/opportunity reads remain public, and no review mutation endpoint is introduced in this issue.
No identity configuration means protected requests fail closed with 503; missing credentials return 401.
Invalid/expired credentials return 401, insufficient permissions return 403, and unavailable key verification returns 503.
Responses do not disclose raw provider errors or token content.

## Signing-key cache and recovery

The asynchronous JWKS cache defaults to 300 seconds (`ARBBOT_AUTH_JWKS_TTL_SECONDS`, 30 to 3600).
Unknown keys can cause a refresh at most once per 30 seconds (`ARBBOT_AUTH_REFRESH_SECONDS`, 1 to 300 and never above the TTL).
Concurrent refreshes share a lock; JWKS retrieval has a five-second timeout, 256 KiB body limit, and at most 64 keys.
Only RSA signing/verification keys from 2048 through 8192 bits are accepted; duplicate identifiers and private-key material invalidate the key set.
A provider should publish replacement keys before using them and overlap old keys through outstanding token lifetimes.
An unknown new key can be rejected until the refresh cooldown ends.
An expired cache is never used when refresh fails; verification remains unavailable until refresh succeeds.
Known keys inside their configured cache lifetime remain usable during a provider outage.
Key removal becomes effective after cache refresh, not immediately.

## Browser and local development

Obtain local development tokens from a development tenant using the same access-token profile and dedicated API audience.
For interactive browser login, use authorization code with PKCE in the identity client; that login flow belongs to frontend identity integration.
There is no local authentication bypass or shared development password.
Deterministic tests generate ephemeral RSA keys and mock JWKS HTTP responses without calling a live provider.

CORS allows only the configured exact origins and the Authorization, Content-Type, If-Match, Accept, and Last-Event-ID headers.
Protected mutations independently reject untrusted or null Origin headers even when a bearer token is valid.
Origin-less command-line/server requests may authenticate with explicit bearer headers; cross-site browser requests lacking Origin are rejected.
Cookies are not accepted as API credentials and credentialed CORS is disabled.
Do not store tokens in browser local storage; prefer a server-side session/BFF integration or short-lived in-memory access tokens as the frontend design requires.
If a BFF later authenticates browser requests with cookies, it must implement its own CSRF defenses, Secure/HttpOnly/SameSite cookie policy, and session expiry before forwarding bearer credentials.
The current bearer-only API does not implement that future session layer.

## Deployment validation still required

Register the production API audience and approved browser origins, restrict reviewer scope grants, configure TLS and secret handling, and test real provider login/rotation/revocation behavior in staging.
Automated tests validate signature failures, required claims, expiry, audience/issuer, viewer/reviewer permissions, audit identity, duplicate headers, cookie rejection, CORS/origin handling, bounded JWKS retrieval, rotation, outage recovery, and unconfigured fail-closed behavior.
Passing fixture-based tests does not prove production tenant configuration.
