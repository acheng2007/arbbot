# Product Goal

Build a complete prediction-market arbitrage discovery platform that continuously ingests data from multiple exchanges, identifies equivalent contracts, evaluates executable arbitrage opportunities, and presents those opportunities through a web interface.

Design the system as a complete product from the beginning.
Keep components modular and independently testable, but do not treat individual components as separate product versions.
Implementation may proceed incrementally while preserving the integrated product architecture and end-to-end workflow.

# Product Scope

- Continuously discover markets and ingest contract metadata, resolution rules, prices, order books, and exchange status.
- Normalize exchange data while preserving source identifiers, original terms, timestamps, and provenance.
- Identify equivalent contracts across exchanges and explain the evidence and uncertainty behind each match.
- Evaluate executable arbitrage using available liquidity, fees, slippage, order constraints, and capital requirements.
- Present opportunities, contract comparisons, execution assumptions, data freshness, and ingestion health through a web interface.
- Persist enough source data and evaluation history to reproduce and audit opportunity calculations.
- Support reliable operation with configuration, monitoring, recovery, and documented setup and deployment.

The product discovers and evaluates opportunities.
Automatic order placement, custody, and fund transfers require explicit scope and authorization before implementation.

# Tech Stack

Build a fullstack application using the following agreed stack.

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | Next.js, React, TypeScript | Dashboard, contract comparisons, opportunity details, and account settings |
| UI | Tailwind CSS, shadcn/ui | Accessible components and responsive layouts |
| Frontend data | TanStack Query, TanStack Table | API state, filtering, sorting, and opportunity tables |
| Backend API | Python, FastAPI, Pydantic | Validated APIs and shared domain models |
| Market-data workers | Python `asyncio`, HTTPX, WebSocket clients | Continuous exchange ingestion, order-book maintenance, and recovery |
| Database | PostgreSQL | Markets, contract mappings, opportunity history, users, and audit records |
| Database access | SQLAlchemy, Alembic | Database models and versioned migrations |
| Browser live updates | Server-Sent Events | Opportunity changes and ingestion status |
| Testing | pytest, Vitest, Playwright | Backend, frontend, and end-to-end validation |
| Local infrastructure | Docker Compose | Reproducible development services |
| Production infrastructure | Container hosting, managed PostgreSQL | Persistent application and worker processes with durable storage |
| Observability | Structured logs, OpenTelemetry, Prometheus/Grafana | Failure diagnosis, ingestion lag, and data freshness monitoring |

Generate the TypeScript API client from FastAPI's OpenAPI schema to reduce frontend and backend contract drift.
Keep financial calculations in Python using `Decimal` and persist exact financial values with PostgreSQL `NUMERIC`.
Transmit exact financial values through APIs as strings to avoid JavaScript floating-point precision loss.
Use PostgreSQL JSONB for exchange metadata where a flexible schema is appropriate.
Introduce Redis when shared caching or worker coordination requires it, while keeping PostgreSQL as the durable source of truth.
Select and pin supported dependency versions during implementation.

# Architecture

Use a modular monolith in one repository with separately runnable web, API, and background worker processes.
Keep shared backend domain logic in a single Python package.
Run continuous ingestion in persistent workers independently of browser sessions and API requests.

Use this repository structure as the starting point:

```text
arbbot/
  apps/
    web/
  backend/
    arbbot/
      api/
      exchanges/
      ingestion/
      matching/
      arbitrage/
      storage/
      workers/
    tests/
  infra/
  docs/
```

Use clear boundaries for exchange adapters, ingestion, normalized storage, contract matching, opportunity evaluation, application APIs, and the web interface.
Choose the simplest architecture that supports reliable continuous operation and future exchanges.
Module boundaries do not require separate services or deployments.
Keep exchange-specific behavior in adapters and expose explicit, validated contracts between components.
Separate deterministic matching and calculation logic from network access, persistence, and presentation.
Treat background processing, persistence, the API, and the interface as parts of the same product.

# Contract Matching

Do not infer equivalence from similar titles alone.
Compare outcomes, payout structures, event definitions, time zones, deadlines, resolution sources, cancellation rules, and exceptional settlement conditions.
Retain the source terms and the rationale for each proposed match.
Distinguish candidate matches, verified equivalence, and rejected matches.
Follow [the accepted candidate-visibility decision](docs/decisions/candidate-visibility.md) when developing matching and presentation.
Expose valid, fresh Jev same-event suggestions as unverified without a probability or confidence admission cutoff; use model scores for ranking and explanation.
Only current automatic evidence and settlement checks can mark a relationship verified, independently of price profitability or financial-input availability.
Explicit contradictions are mismatches; missing evidence remains unverified with reasons.
Keep potential price gaps separate from qualified arbitrage estimates, and retain financial, freshness, source-invalidation, and operator-veto gates.
This is the required development direction; do not claim its implementation is complete until matching, APIs, monitoring, and browser acceptance demonstrate it.
Exclude unresolved semantic differences from opportunities presented as executable arbitrage.

# Opportunity Evaluation

Use executable bid and ask prices and order-book depth rather than last-trade prices or midpoints.
Calculate size-dependent net results after applicable fees, slippage assumptions, rounding, minimum order sizes, and other exchange constraints.
Use decimal or integer monetary representations with explicit units and precision.
Verify the combined payoff across all relevant settlement outcomes.
Distinguish theoretical price discrepancies from opportunities supported by current executable quotes.
State capital, balance, inventory, and venue-access assumptions when those conditions cannot be verified.
Expose quote age, cross-exchange timing differences, partial-fill risk, and execution uncertainty.
Do not present estimated profitability as guaranteed profit.

# Ingestion and Reliability

Make ingestion idempotent and support reconnects, bounded retries, rate limits, backoff, and recovery after interruption.
Track source timestamps and receipt timestamps separately.
Detect stale, incomplete, out-of-order, and invalid data before it reaches opportunity evaluation.
Resynchronize order books when sequence gaps or integrity failures occur.
Surface degraded exchange connectivity and suppress or clearly invalidate affected opportunities.
Keep credentials out of source control, logs, and browser bundles.
Use recorded fixtures and explicit simulation modes for reproducible development without presenting synthetic data as live data.

# Web Experience

Make each opportunity understandable through its venues, contracts, trade directions, available size, capital requirement, costs, net payoff, freshness, and matching rationale.
Provide useful loading, empty, stale-data, and error states.
Support inspection of underlying contract terms and calculation assumptions.
Use accessible, responsive layouts and scrutinize the interface during end-to-end validation.

# Engineering and Validation

Prioritize simplicity, quality, robustness, scalability, and long-term maintainability over short-term development cost.
Keep components independently testable and validate the integrated path from exchange data through matching and evaluation to the rendered interface.
Cover settlement edge cases, fee calculations, depth-dependent sizing, rounding, stale data, reconnects, duplicate updates, and partial exchange outages with meaningful tests.
Verify current exchange documentation before relying on API behavior, fee schedules, or resolution semantics.
Document chosen technologies, supported exchanges, configuration, local startup, checks, deployment, and operational limitations as they are implemented.
Do not invent commands or claim checks passed when they have not been run.

Always begin a bug fix by reproducing the reported behavior in an end-to-end setting before changing code.
If true end-to-end reproduction is unavailable, explain the limitation and use the closest user-facing reproduction possible before editing.
Use the reproduction to identify the actual root cause and verify the completed fix.
During end-to-end testing, scrutinize the UI and aim for pixel-perfect results.
Fix clear quality problems outside the immediate task when the fix is safe and reasonably scoped, and mention the additional change.

# Session Handoff

Whenever you finish a task, update the relevant handoff file with the concrete next step before ending the session.
Use `docs/contributing/frontend-handoff.md` for frontend workstreams, or create or update a matching handoff under `docs/contributing/` for other workstreams.
Record what was completed, the current branch or PR if any, blockers, and the single clearest next action for the following agent or chat.
Commit the handoff update (along with the finished work when applicable) before stopping.
Do not leave unfinished work without a committed next-step handoff.

# Writing and Git

Never use em dashes; use standard hyphens instead.
When writing substantially long Markdown files, put each complete sentence on its own line.
When creating commits, use only the user's configured Git identity as author and committer.
Never add an agent name or an AI or tool identity as an author, committer, co-author, or commit trailer.
