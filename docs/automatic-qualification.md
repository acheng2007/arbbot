# Automatic settlement qualification

Live discovery defaults to automatic evidence rules through `ARBBOT_AUTOMATIC_QUALIFICATION=true`.
Human drafts, settlement decisions, applicability approvals, and account profiles are not prerequisites for this path.
Jev continues to discover counterparts and supply advisory semantic findings; its confidence cannot qualify a contract.
The system discovers and calculates conditional estimates only; it does not place orders.

## Two result feeds

`GET /api/v1/potential-opportunities` returns fresh, depth-supported ordinary-outcome price gaps for established counterpart events or fresh Jev-supported candidates.
These assume complementary ordinary outcomes and do not establish the payout in exceptional states.
Unknown fees, collateral, or execution constraints produce null net-spread and capital fields, never zero-cost assumptions.
A settlement-qualified pair can remain potential while financial inputs are unavailable.
Explicit event contradictions and operator vetoes exclude potential results.
Potential results never appear in the qualified opportunities endpoint.
The potential feed streams ranked rows and stops after enough currently eligible rows fill the requested page.

`GET /api/v1/opportunities` returns positive worst-case conditional estimates supported by current automatic settlement assessments, public fees, native instrument constraints, and fresh quotes.
Both legs undergo an immediate quote recheck before publication.
Fees, slippage, capital limits, minimum sizes, quote age/skew, exchange health, and exceptional payouts remain gates.
Access, prefunded balances, borrowing availability, and account-specific surcharges are disclosed assumptions.
Known installation restrictions are explicitly disclosed and cannot establish user executability.
No API estimate guarantees fills or profit.

The existing browser receives compatible generated contracts but does not yet implement the new potential feed or qualification inspection workflow.
A nullable-review compatibility guard prevents an automatic estimate from being dereferenced as a human review.
Existing match badges identify automatic qualification without claiming a human review.
The public API is the complete supported interface for the new workflow in this change.

## Evidence and supported interpretation

An immutable assessment binds the pair, source terms, document generations, normalized definitions, policy/provider versions, exact payout scenarios, evidence IDs, start/completion times, and expiry.
The automatic settlement model has no human reviewer identity.
Source quotations must occur in captured documents associated with the instrument.
Indexes, filenames, and similar titles are insufficient proof of product applicability.
Changed or failed shared documents invalidate dependent assessments, including changes captured through another market.
A newly appended unsupported document clause remains incomplete even when old quotations are still present.

Versioned family rules recognize CPI, core CPI, Fed rate-hike, and MLB championship identities using the existing extractors.
Complete automatic interpretation currently uses a closed, explicit product-description grammar for named canonical fields and settlement-policy statements.
All required fields and cancellation, fallback, and ambiguous-resolution policies must be accounted for.
Canonical exceptional policy conditions and payouts must match, and explicit captured-document event contradictions exclude the pair.
Unrecognized lines, missing fields, conflicting values, unsupported payout/source conventions, or unmodeled document language cause abstention.
No missing exceptional policy is inferred to be inapplicable.
Existing natural-language identity extraction alone does not provide full settlement compatibility.

This is deliberately limited production interpretation coverage, not universal natural-language contract understanding.
The 30 authentic Kalshi/US benchmark pairs retain incomplete settlement interpretation and missing applicable exceptional evidence.
They have not been promoted to qualified estimates.
The successful end-to-end positive examples use explicitly synthetic complete contracts, recorded public fee documents, and synthetic instrument/document bindings.
Recorded bindings cannot be attached to authentic contracts.
They demonstrate automated plumbing and gates, not the accuracy or completeness of real settlement interpretation.
Extend source capture and versioned provider grammars using authentic documents to increase production coverage without per-pair human approval.

All independent combinations of exceptional and ordinary settlement states are enumerated conservatively.
Identical cancellation wording does not prove that both venues must cancel together.
No exceptional joint state is excluded by the initial automatic policy.
An automatically qualified settlement relationship may therefore have no profitable worst-case size.

## Scheduling and recovery

The existing persistent worker supervises qualification independently of books, catalog discovery, fees, matching, and Jev.
Four qualification tasks consume a durable coalesced queue bounded to 512 pending/running pairs.
A durable catalog cursor rotates work beyond the queue limit.
PostgreSQL serializes the worker process with the existing advisory lock.
Restart recovers running jobs; a sixty-second job lease also permits retry after a failed task.
Unavailable provider findings retry after thirty seconds, with expiry checked by a one-second renewal supervisor.
Matching notifications are coalesced through existing in-process events.
No additional service is required.

Successful supported, incomplete, or incompatible assessments cache for at most 24 hours, bounded by document validity and market close.
An unchanged document receipt does not rerun settlement interpretation.
Quotes, fee captures, and account records are not qualification cache inputs.
Terms, document content/generation/availability, explicit vetoes, and rule/provider versions are inputs.
Every current read rechecks identity; transaction guards recheck and lock evidence before publishing.
Late results remain immutable audit history and cannot become current advice.
Publications must use the exact settlement model of the current assessment.

Book-driven evaluation does not wait for the catalog interval or a model response.
The default book poll remains five seconds, and catalog discovery remains separately bounded.
The new synthetic two-market tests require stored-book potential publication and qualification-triggered evaluation within two seconds.
These scoped measurements do not promise catalog-wide live exchange latency.
Discovery, source retrieval, provider pacing, monitoring budgets, and queue depth can delay coverage.

## Public contracts and history

- `GET /api/v1/matches?qualification=qualified&limit=100&offset=0` applies fresh qualification filtering and ranking before pagination.
- `GET /api/v1/matches/{match_id}/qualification` returns the current qualification summary.
- `GET /api/v1/matches/{match_id}/qualification?assessment_id=...` explicitly returns historical, stale status.
- `GET /api/v1/matches/{match_id}/qualification/history` returns paginated immutable assessments and supplied inputs.
- `GET /api/v1/potential-opportunities` returns a separate paginated conditional-gap feed, sorted by gross spread.
- `GET /api/v1/potential-opportunities/{id}?historical=true` permits explicit audit inspection of a withdrawn gap.
- `GET /api/v1/status` reports queue/running counts, last successful assessment, sanitized errors, and last-assessed coverage independently of exchange health.
- SSE snapshots add qualification health and potential results using the existing refresh mechanism.

Qualification states are `pending`, `qualified`, `incomplete`, `incompatible`, `stale`, and `unavailable`.
`qualified` describes settlement assessment; financial gates still determine whether an opportunity exists.
The legacy match status `verified` is retained for compatibility and can now have an `automatic_rules` qualification basis.
New automatic opportunities have a settlement model and assessment reference with `review=null`.
Historical payloads without these fields remain readable.
Historical human decision APIs remain available for optional intervention and audit.
Explicit rejection or revocation remains a veto until cleared, including while automatic work is pending.
Authenticated operators can submit `action="cleared"` to the existing revision-aware review endpoint with the previous decision and draft IDs, a reason, and no approval payload.
Clearing a veto permits automatic qualification to resume; it does not itself qualify settlement or revive a published estimate.

Migration `b025_qualification` adds immutable assessment runs, durable jobs/current references, and potential-calculation history.
Existing review and opportunity payloads are preserved.
Financial columns use `NUMERIC`, and APIs serialize exact financial values as strings.

## Adding another platform

Register the venue in `arbbot.venues.VENUES` with an adapter factory and typed capabilities.
Venue identities use validated registered strings rather than a fixed three-platform enum.
Provide an evidence resolver that proves exact document applicability, parses supported source language, and returns evidence IDs, normalized definitions, missing-evidence reasons, expiry, and a version.
Declare public source hosts in the registration; source readers retain bounded requests and reject arbitrary unregistered hosts.
Provide public fee refresh and its assumed account class.
A new fee curve registers a validator and exact Decimal bound in `arbbot.fees.executable.FORMULAS`.
Existing binary USD curves can be reused when documented.
Adapters normalize native prices, minimums, increments, actions, and collateral into the shared contracts.
The evaluator derives native prices and short collateral from normalized semantics, independently of venue names.
The current shared financial model supports binary USD unit payouts and complementary outcomes; other payout systems require an explicit financial-model extension.

Contract-family rules consume normalized markets and evidence rather than exchange-pair names.
Version provider and family changes so current assessments invalidate automatically.
A test-only fourth registered platform exercises qualification, fees, evaluation, publication, API filtering, and invalidation without a new evaluator branch.

## Configuration and checks

Set `ARBBOT_AUTOMATIC_QUALIFICATION=false` only to use the historical review-driven workflow.
The historical recorded browser harness sets this explicitly; its checks continue to test historical review behavior.
The automatic harness is separate and seeds no human records.
OpenRouter configuration, pinned Jev model, two requests per second, provider backoff, and advisory boundaries are unchanged.
No OpenRouter key is needed for deterministic automatic qualification.

```sh
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
.venv/bin/pytest backend/tests -q
ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@127.0.0.1:55432/arbbot .venv/bin/pytest backend/tests -q
.venv/bin/python backend/scripts/run_automatic_acceptance.py --output /tmp/arbbot-automatic-acceptance
.venv/bin/python -m arbbot.api.export_schema --output docs/openapi.json
npm run generate:api --prefix apps/web
npm run generate:api:check --prefix apps/web
```

The automatic harness runs an isolated PostgreSQL schema, real persistent worker, and HTTP API against an offline recorded transport with no network fallback.
It retains logs, diagnostics, and a result report in the supplied directory.
The preserved schema permits further inspection.
The harness verifies automatic estimates, the separate potential feed, pagination, public fee outage/recovery, uninterrupted book polling, source-change invalidation/recovery, historical assessment access, and worker restart.

Official references checked during implementation: [Kalshi series metadata](https://docs.kalshi.com/api-reference/market/get-series), [Polymarket US market metadata](https://docs.polymarket.us/api-reference/markets/get-market-by-slug), and [Polymarket US public fees](https://docs.polymarket.us/fees).
These establish public API and fee inputs, not settlement equivalence of any specific counterpart pair.
