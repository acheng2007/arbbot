# Implementation roadmap

Updated October 15, 2026 against the committed implementation on `backend/completion`.
This roadmap describes one integrated product: continuously find cross-exchange prediction-market opportunities, explain their economics and uncertainty, and surface useful results without waiting for human approval.
The [system design](system-design.md) defines component boundaries and the target workflow.
The [project status handoff](contributing/project-status-handoff.md) records implementation evidence and the next action.

## Product direction

Prioritize Kalshi and Polymarket US, with an architecture that admits additional venues through registered capabilities and adapters.
Keep Polymarket International as a distinct integration and research route; never present it as Polymarket US.
Discover broadly, monitor complete counterpart pairs within explicit budgets, and disclose the coverage those budgets permit.
Venue count is driven by useful overlap, supported instruments, source evidence, and operating reliability.

Human review is optional operator tooling, not a prerequisite for discovery, settlement qualification, or public conditional estimates.
No account connection or balance verification is required to browse public results.
Public results disclose account access, capital, borrowing, and fee-class assumptions; they do not establish a particular user's ability to execute.
Known restrictions must remain visible.
Order placement, custody, transfers, and private account integration remain outside this roadmap.

The product has two result feeds:

- **Potential price gaps:** fresh depth supports an ordinary-outcome spread, with unresolved settlement or financial inputs stated explicitly.
- **Qualified estimates:** automatic source-backed settlement assessment, complete supported payout scenarios, current public fees, instrument constraints, and immediately rechecked quotes support a positive worst-case conditional estimate.

Neither feed promises a fill or guaranteed profit.
A model suggestion alone cannot produce a qualified estimate.
An empty qualified feed is a valid result, but persistent low coverage is a product gap to measure and address.

## Accepted direction: visible suggestions with automatic verification

The [candidate-visibility decision](decisions/candidate-visibility.md) governs matching and presentation.
Expose every valid current Jev same-event suggestion as Unverified, use scores for ranking rather than admission, mark complete compatible automatic settlement evidence Verified, and show explicit contradictions as Mismatch.
Qualified arbitrage estimates additionally require positive current financial checks; verification alone does not imply profitability.
The broad-discovery implementation applies this policy across matching, API queries, monitoring, and browser views.

## Implemented baseline

Checked items describe implemented scope, not proof of live profitability or unrestricted venue support.

- [x] Separate Next.js web, FastAPI API, persistent asyncio worker, PostgreSQL storage, and additive Alembic migrations.
- [x] Kalshi, Polymarket US, and separate Polymarket International adapters; registered venue identities and capabilities.
- [x] Broad catalog traversal, durable continuation, bounded pair monitoring, watchlist priorities, and fair rotation within monitoring tiers.
- [x] Immutable captured sources, document generations, original terms, quote provenance, and missing-evidence states.
- [x] Deterministic event retrieval and partial CPI, core CPI, Fed, and MLB family interpretation.
- [x] Jev advisory counterpart and clause classification with bounded retrieval, durable jobs, caching, source invalidation, and independent provider health.
- [x] Automatic qualification without human records, with immutable assessments, versioned evidence rules, durable jobs, expiry, and guarded publication.
- [x] Separate persisted potential-price-gap and qualified-estimate APIs, current/history access, filtering before pagination, and snapshot notifications.
- [x] Public fee refresh, Decimal depth-based sizing, native short/collateral semantics, conservative exceptional payouts, and immediate pre-publication quote rechecks.
- [x] Publication and read-time checks for changed sources, assessments, fees, quotes, vetoes, and venue health.
- [x] Compact paired-market dashboard, catalog-wide filters, paginated counterparts, exact-ID comparisons, source inspection, and advisory Jev details.
- [x] Existing opportunity screens tolerate automatic assessments and identify their basis correctly.
- [x] Authenticated historical review APIs and optional operator veto/clear actions.
- [x] Recorded worker/API acceptance, SQLite/PostgreSQL suites, generated API contracts, frontend units, and desktop/mobile fixture browser coverage.
- [x] Structured logging, API metrics, opt-in tracing, Docker Compose, and CI workflow definitions.

## Current delivery limits

The automatic backend/API and browser now expose separate Potential and Qualified views, full assessment inspection, and filtered category coverage.
Complete settlement interpretation currently accepts a closed explicit source-language grammar.
All 30 authentic Kalshi/US benchmark pairs remain incomplete because supported interpretation or applicable exceptional-settlement evidence is missing.
Positive automatic acceptance examples are explicitly synthetic complete contracts with synthetic instrument/document bindings and recorded public fee documents.
They establish workflow correctness, not real-pair qualification coverage.

The Jev benchmark records eight of nine labeled same-event counterparts retrieved by the deterministic baseline, 21 different-event pairs, and insufficient exceptional-settlement evidence across all 30 pairs.
The [October 15 live-provider benchmark](contributing/jev-live-benchmark-2026-10-15.json) completed all 30 pairs without errors and matched every raw event label, but added no candidates at the current thresholds; assisted recall stayed eight of nine.
This is a small recorded sample, not proof of general accuracy or settlement compatibility.
The corpus also lacks authentic uncertain event-identity labels.
Broader venue streaming, production latency measurements, staging operations, and a forward paper study remain unfinished.

## Milestone 1: useful automatic discovery on authentic contracts

Make the current automation useful with real source evidence and expose its results clearly through the browser.
The first integrated delivery is the accepted suggestion-visibility policy across matching, APIs, monitoring, and the browser.
Continue authentic evidence/provider coverage alongside it; visible Unverified comparisons do not depend on achieving complete settlement interpretation first.

- [x] Replace score-based Jev suggestion admission across current-result storage, matching, monitoring, and APIs; retain validity, deterministic independence, contradictions, and veto handling.
- [x] Display all current suggested comparisons as Unverified or Verified with explicit Mismatch and stale/history inspection; use scores only for ranking and explanation, and apply status filters before pagination.
- [x] Prove low-score suggestion visibility, independent automatic verification/profitability, incomplete/provider states, and financial-gate preservation through connected desktop/mobile acceptance.
- [ ] Capture authentic instrument-to-specification relationships, rulebooks, amendments, and authoritative resolution evidence for an initial supported Kalshi/US family.
- [ ] Extend versioned applicability providers and source-language interpretation using captured authentic wording, including changed-document and unknown-clause abstention.
- [x] Report qualification coverage and blocker counts over the authentic corpus, including incompatible and incomplete pairs; do not silently drop difficult cases.
- [x] Add separate Potential and Qualified browser views, qualification reasons, evidence/history inspection, and pending/stale/unavailable states.
- [x] Keep original terms and model advice accessible, with model suggestions visually distinct from automatic qualification and legacy human review.
- [x] Connect both feeds to snapshot refresh and server-side filtering/pagination without resetting navigation or selected comparisons.
- [x] Extend the recorded PostgreSQL/worker/API/Next.js browser harness to the new automatic workflow on desktop and mobile with zero required human review records.
- [ ] Validate source-change invalidation, fee/provider outage and recovery, quote expiry, veto clearing, and independent book polling through the rendered UI.

**Exit criteria:** broad authentic contracts are discoverable and assessable without per-pair human setup, results expose evidence gaps and understandable blockers, and the UI faithfully separates potential from qualified results.
Demonstrate authentic qualification when complete compatible evidence permits it; otherwise record the exact unresolved clauses and keep expansion of real coverage open.
A synthetic positive fixture does not establish authentic qualification coverage.
A profitable real pair is not required.

## Milestone 2: speed and coverage that can be measured

Optimize the existing persistent pipeline around changed inputs and useful complete pairs.
Do not wait for Jev or source interpretation to refresh already qualified prices.

- [ ] Measure cold discovery, source capture, queue wait, interpretation, warm recalculation, publication, API, and browser render separately.
- [ ] Establish p50/p95/p99 latency and throughput under a declared catalog size, monitoring budget, and provider latency profile.
- [ ] Target warm stored-book potential publication and assessment-completion-to-publication within two seconds at p95 under the declared workload; retain independent quote age/skew gates.
- [ ] Measure receipt-to-browser latency and set a browser delivery budget from the observed SSE/query path rather than claiming the two-second backend target is end to end.
- [ ] Improve bounded change-triggered evaluation and add supported US streaming adapters where official capabilities permit, preserving REST resynchronization and independent task supervision.
- [ ] Measure monitored counterpart coverage, time since each pair was refreshed, queue age, and starvation; preserve complete-pair scheduling and tier rotation.
- [x] Run the initial live Jev smoke and 30-pair authentic recorded benchmark, retaining actual answers, model identity, retrieval results, and provider usage.
- [ ] Extend live Jev evaluation with authentic ambiguous identities and applicable clause evidence, and instrument latency and omitted-context effects to assess ranking quality without restoring a score-based suggestion-visibility cutoff.
- [ ] Expand the labeled corpus with authentic uncertain event identity, differing seasons/thresholds, cancellation conflicts, and source amendments; keep synthetic edge cases separate.

**Exit criteria:** repeatable load and outage runs satisfy declared latency/freshness targets without weakening settlement or financial checks, and coverage/quality reports include failures and exclusions.
The existing two-second synthetic warm assertions are regression evidence only, not a production service-level claim.

## Milestone 3: add venues and families through capabilities

Expand useful supported overlap after the initial authentic workflow is measurable.
Do not add a platform solely to increase the venue count.

- [ ] Assess each proposed venue's public data, native instruments, source applicability, fees, access restrictions, depth semantics, and recovery behavior using current official evidence.
- [ ] Implement catalog/books/source adapters, versioned fee and evidence providers, and declared execution constraints through existing registry boundaries.
- [ ] Register family-specific interpretation separately from venue-specific data retrieval so shared event semantics do not create pairwise venue branches.
- [ ] Exercise a new venue against every relevant existing venue through generic retrieval, qualification, sizing, storage, API, and browser contracts.
- [ ] Require recorded positive/negative cases, authentic evidence coverage, outage/resync tests, migration preservation, and generated-contract checks before enabling supported evaluation.
- [ ] Keep discovery-only support explicit when settlement, fees, or instruments are unsupported.

**Exit criteria:** adding a venue requires no venue-specific branch in the financial evaluator or browser result model, and its supported capabilities and coverage limits are inspectable.
The existing test-only fourth venue demonstrates the extension path; it is not a live exchange integration.
Opinion and Limitless remain outside the current US priority; other candidates require their own capability assessment.

## Milestone 4: operate and evaluate the product continuously

Operational instrumentation starts with the earlier milestones; production rollout waits for measured behavior and recovery evidence.

- [ ] Verify hosted CI for the publication head rather than relying on historical successful runs.
- [ ] Add worker queue/coverage metrics, provider health, stale-feed and withdrawal alerts, and dashboards for the full source-to-browser path.
- [ ] Deploy reproducible staging with backend-only secrets, TLS, restricted database access, and authentication for operator mutations.
- [ ] Rehearse migrations, rollback-compatible deployment, backup restore, worker restart, source failure, and partial venue outage.
- [ ] Run a seven-day forward paper study with fixed monitoring/capital/slippage settings and complete records of candidates, rejected results, quote rechecks, withdrawals, and opportunity lifetimes.
- [ ] Report qualification coverage, conditional estimated value, fee sensitivity, freshness, and missed coverage without treating paper estimates as realized returns.

**Exit criteria:** the deployed stack recovers without manual reapproval, its results can be reproduced from stored inputs, and the paper-study report separates observed prices from hypothetical fills.

## Validation baseline and planning rules

The [automatic acceptance report](contributing/automatic-qualification-acceptance-2026-10-14.json) records 566 passing tests on each backend database, supplemental source/pagination checks, 66 frontend unit tests, and 66 desktop/mobile fixture tests.
It also records type, lint, generated-contract, build, and recorded automatic worker/API results.
The subsequent October 15 live Jev benchmark is separate evidence for event classification on recorded metadata; it does not extend settlement qualification coverage.
Those checks were run for the implementation, not rerun for this documentation update.
The broad-discovery handoff records the subsequent connected automatic desktop/mobile acceptance and current limitations.

Keep the agreed stack and a modular monolith with independently supervised worker tasks.
Do not introduce Redis, a second generative model, or additional services without an observed coordination or throughput need.
Historical issue scopes in the [contributor index](contributing/README.md) remain traceability records; their review-first dependencies no longer define the critical path.
Optional review tooling and private execution-readiness work do not block public discovery.

**Next action:** run a sustained live Kalshi/US coverage study across categories, using recorded blockers to prioritize authentic source-applicability and settlement-language extensions.
