# Arbbot

Arbbot is a fullstack prediction-market arbitrage discovery platform.
The backend provides continuous read-only Kalshi and Polymarket ingestion, candidate matching, reviewed settlement equivalence, conservative opportunity evaluation, durable audit history, and a web-ready API.
The frontend has not been implemented yet.

## Run the backend

Install Docker with Compose, then run from this directory:

```sh
docker compose up --build -d
```

This starts PostgreSQL, applies migrations, and launches separate API and worker containers.
The default is **simulation mode**, with two synthetic contracts and a reproducible opportunity.
Simulation data is labeled in API responses and isolated from live data.

- API documentation: <http://localhost:8000/docs>
- API readiness: <http://localhost:8000/health/ready>
- Ingestion status: <http://localhost:8000/api/v1/status>
- Current opportunities: <http://localhost:8000/api/v1/opportunities>
- Live updates: <http://localhost:8000/api/v1/stream>

Verify the complete running workflow:

```sh
docker compose exec -T api python scripts/smoke.py
```

Inspect logs and stop services without deleting stored data:

```sh
docker compose logs --tail=100 api worker
docker compose down
```

The Compose credentials are local development defaults and services bind to localhost.
The current API is read-only and does not implement user accounts or authorization.
Production deployment needs managed secrets, restricted database access, TLS, and an authenticated gateway.

## Python development

Python 3.14 is used by the tested container configuration.
Run these commands from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e backend
docker compose up -d db
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Start the API and worker in separate terminals:

```sh
.venv/bin/uvicorn arbbot.api.app:app --host 127.0.0.1 --port 8000 --reload
```

```sh
.venv/bin/arbbot-worker
```

For a single ingestion and evaluation cycle, use `.venv/bin/arbbot-worker --once`.
Do not run a local worker alongside the Compose worker against the same database.
A PostgreSQL advisory lock enforces one active ingestion worker per database.

Copy `.env.example` to `.env` to customize local Python processes.
Configuration uses the `ARBBOT_` prefix and is validated at startup.
Compose explicitly configures its database URL and mode; other host environment variables are not automatically forwarded to containers.
See [backend operations](docs/backend.md) for live configuration and current boundaries.

## Checks

```sh
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/pytest -q backend/tests
.venv/bin/alembic -c backend/alembic.ini check
```

Unit and integration tests use isolated temporary SQLite databases and mocked exchange HTTP responses.
To exercise the same persistence and API tests against local PostgreSQL, run:

```sh
ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot .venv/bin/pytest -q backend/tests
```

Each PostgreSQL test creates and removes its own uniquely named schema without modifying application tables.
The Docker smoke test exercises real PostgreSQL, the independent worker, REST endpoints, historical source records, and SSE over HTTP.
Live exchange reads are separate from deterministic tests.

## Repository

```text
backend/
  arbbot/
    api/          FastAPI endpoints and schema export
    arbitrage/    Pure depth, cost, capital, and payoff calculations
    exchanges/    Kalshi, Polymarket, and simulation adapters
    ingestion/    Ingestion and evaluation orchestration
    matching/     Candidate matching and settlement review
    storage/      SQLAlchemy models and repositories
    workers/      Continuous worker and single-cycle entry point
  migrations/     Alembic schema history
  scripts/        Running-system verification
  tests/          Deterministic automated tests
infra/            Backend container definition
docs/             Operations, API, and review documentation
```

Runtime and development dependencies are pinned separately in `backend/requirements.lock` and `backend/requirements-dev.lock`.
The backend is one Python package with separate runtime processes, preserving a modular monolith architecture.

See [structured contract matching](docs/contract-matching.md) for evidence-backed event definitions, settlement comparisons, and the live review workflow.

Automatic partial US CPI definitions are available at `GET /api/v1/markets/{market_id}/extraction` and feed candidate matching.
Unsupported and missing terms remain explicit; live approval still requires a human-reviewed complete definition.

Track completed work and upcoming dependencies in the [implementation roadmap](docs/implementation-roadmap.md).
See [recorded contract validation](docs/recorded-contracts.md) for real metadata fixtures and extraction coverage.

Contributors: start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [modular issue index](docs/contributing/README.md).

## Frontend development

The Next.js foundation lives in `apps/web` and requires Node.js 22.12 or newer.
Install the pinned dependencies and start it locally:

```bash
cd apps/web
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.
Set `BACKEND_URL` in `apps/web/.env.local` to the backend HTTP(S) base URL, defaulting to `http://localhost:8000`, and restart Next.js after changing it.
The server reads this value at runtime; it is never included in browser bundles.
The browser talks only to same-origin routes under `/api`, which proxy the backend server-side.
Start the backend using the Docker Compose instructions above to verify the connection.
The connection page reports backend liveness and its reported simulation/live mode, not exchange readiness.

### Working without a backend

Set `ARBBOT_WEB_DATA_SOURCE=fixtures` to serve every screen from the recorded dataset in `src/lib/api/fixtures.ts`:

```bash
ARBBOT_WEB_DATA_SOURCE=fixtures npm run dev
```

Fixture mode is opt-in, and any other value reads the real backend, so recorded data can never stand in for live data by accident.
Every screen served this way carries a `Recorded fixture data` banner stating that no exchange or backend was contacted.
Browser tests always run in this mode, so they need no database, backend, or exchange credentials.

### Generated API client

`src/lib/api/schema.ts` is generated from the committed `docs/openapi.json` and must not be edited by hand:

```bash
npm run generate:api
npm run generate:api:check
```

The check fails if the committed client has drifted from the OpenAPI document, and `npm test` runs it.
Monetary and quantity fields are generated as `DecimalString` and stay exact strings from the API through to the rendered page; nothing converts them to a JavaScript number.

```bash
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright runs desktop and mobile Chromium checks against a local web server on port 3100 backed by recorded fixtures.
No exchange, backend, or database is contacted.
Use `npm run build` followed by `npm start` to run the production application.
Shared shadcn-style primitives and theme tokens live in `src/components/ui` and `src/app/globals.css`; `components.json` configures future shadcn additions.
Feature screens live under `src/features`, with routes in `src/app`.

| Route | Purpose |
| --- | --- |
| `/opportunities` | Backend-calculated estimates with costs, payout scenarios, expiry, and live connection status |
| `/matches` | Proposed contract pairs with side-by-side settlement terms and source quotations |
| `/markets` | Discovered markets with original terms, extracted facts, and quote health |

Authenticated draft editing and review actions are not implemented; those depend on the backend review APIs.
