# Development and verification

Run commands from the repository root unless a block explicitly changes directory.
See the [README](../README.md) for the product overview and Docker quick start, and [system design](system-design.md) for runtime boundaries.
Dependencies are pinned in the backend lockfiles and frontend package lockfile.

## Docker simulation

Install Docker with Compose and run:

```sh
docker compose up --build -d
docker compose exec -T api python scripts/smoke.py
```

Wait for migrations and the first worker cycle before running the smoke test.
The stack starts PostgreSQL, migrations, API, worker, and web in simulation mode.
The two synthetic contracts and their reproducible opportunity are labeled and isolated from live records.
The simulation includes a synthetic review fixture; it does not exercise authentic automatic settlement interpretation.
The smoke script checks PostgreSQL-backed worker results, exact financial strings, REST endpoints, historical terms, and snapshot SSE.

| Address | Purpose |
| --- | --- |
| `http://localhost:3000/markets?view=all` | Synthetic markets and their quotes |
| `http://localhost:3000/opportunities` | Conditional opportunity estimates |
| `http://localhost:3000/matches` | Contract comparisons |
| `http://localhost:8000/docs` | Interactive OpenAPI documentation |
| `http://localhost:8000/health/ready` | API readiness |
| `http://localhost:8000/api/v1/status` | Ingestion and provider health |
| `http://localhost:8000/api/v1/stream` | Snapshot SSE |
| `localhost:55432` | Default local PostgreSQL |

The minimal simulation fixture is excluded by the default paired-market filter.
Use All markets for its quotes or Opportunities for its reproducible calculation; the richer frontend fixture dataset provides the paired dashboard shown in the README.

```sh
docker compose logs --tail=100 api worker
docker compose down
```

Stopping preserves stored data.
Development services bind to localhost and use local default database credentials.
Production deployment still requires managed secrets, TLS, restricted database access, and configured operator authentication.

## Python development

The container and backend CI use Python 3.14; the package declares Python 3.12 or newer.
Install the pinned development environment and migrate the local database:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e backend
docker compose up -d db
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Copy `.env.example` to `.env` if it does not already exist and adjust local settings.
Start API and worker in separate terminals:

```sh
.venv/bin/uvicorn arbbot.api.app:app --host 127.0.0.1 --port 8000 --reload
```

```sh
.venv/bin/arbbot-worker
```

Use `.venv/bin/arbbot-worker --once` for one ingestion/evaluation cycle.
Do not run a local worker alongside the Compose worker against the same database.
A PostgreSQL advisory lock enforces one active ingestion worker per database.

Settings use the `ARBBOT_` prefix and are validated at startup; the OpenRouter key uses `OPENROUTER_API_KEY`.
Compose explicitly configures container settings, including its database URL and mode; arbitrary host variables are not automatically forwarded.
See [backend operations](backend.md) and [automatic qualification](automatic-qualification.md) for configuration boundaries.

## Frontend development

Use Node.js 22.13 or newer and npm 11.6.2, as declared in `apps/web/package.json`.

```sh
cd apps/web
npm ci
cp .env.example .env.local
npm run dev
```

Copy the environment example only when `.env.local` does not already contain local configuration.
Set `BACKEND_URL` to the backend HTTP(S) base URL, defaulting to `http://localhost:8000`, and restart Next.js after changing it.
The server reads this setting; it is not bundled into the browser.
Browser reads use the same-origin API proxy.
The connection page reports backend liveness and its mode, not the freshness of exchange books.

To explore the interface without a backend:

```sh
cd apps/web
ARBBOT_WEB_DATA_SOURCE=fixtures npm run dev
```

If already in `apps/web`, omit the `cd` line.
Fixture mode uses `src/lib/api/fixtures.ts` and labels screens as recorded fixture data, not tradable.
No exchange or backend is contacted in this mode.
The README screenshot was captured from this existing dataset without changing prices or verification states.
It includes a legacy synthetic review example and an International venue, independently of the US live-demo defaults.

Use `npm run build` followed by `npm start` for the production frontend build.
The latest recorded verification used `npm run build -- --webpack`; the package's default build command remains `npm run build`.
Feature screens live under `src/features` and routes under `src/app`.
Shared UI primitives and tokens live under `src/components/ui` and `src/app/globals.css`.

## Generated API contracts

The TypeScript schema is generated from `docs/openapi.json`; do not edit it by hand.
From the repository root:

```sh
.venv/bin/python -m arbbot.api.export_schema --output docs/openapi.json
cd apps/web
npm run generate:api
npm run generate:api:check
```

Regeneration changes tracked files and belongs in the same commit as intentional API changes.
Monetary and quantity fields use exact decimal-string contracts; preserve that representation in frontend data handling.
The generated-client check is a separate command and CI step; `npm test` runs Vitest.

## Backend checks

```sh
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/pytest -q backend/tests
.venv/bin/alembic -c backend/alembic.ini check
```

Default tests use temporary SQLite databases and mocked/recorded external responses.
Run the persistence and API suite against local PostgreSQL with:

```sh
ARBBOT_TEST_DATABASE_URL=postgresql+psycopg://arbbot:arbbot@localhost:55432/arbbot .venv/bin/pytest -q backend/tests
```

PostgreSQL tests create and remove isolated schemas without modifying application tables.
Run migrations before checking Alembic model drift against the application database.
Live exchange reads are separate from deterministic test results.

## Frontend checks

```sh
cd apps/web
npm run generate:api:check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Fixture browser tests run desktop/mobile Chromium on port 3100 without a backend or exchange credentials.
Ensure another server on that port is not serving a different data source.
Failure traces and screenshots are retained under `apps/web/test-results`.
Backend and frontend CI definitions live in `.github/workflows`.
Their existence is not evidence that the current commit passed hosted checks.

## Recorded connected acceptance

With PostgreSQL available, run the automatic backend/API harness from the repository root:

```sh
.venv/bin/python backend/scripts/run_automatic_acceptance.py --output /tmp/arbbot-automatic-acceptance
```

It runs the real persistent worker and HTTP API against explicitly synthetic complete contracts, synthetic document bindings, and recorded public fee responses.
It checks automatic qualification without human records, potential results, invalidation, outages/recovery, and restart.
It does not implement or verify the planned automatic qualification/potential browser screens.
See [automatic qualification](automatic-qualification.md) for its configuration and evidence boundary.

The separate connected harness covers the existing review-driven browser flow and optional offline Jev response replay:

```sh
.venv/bin/python backend/scripts/run_acceptance.py --classification --output /tmp/arbbot-jev-acceptance
```

Install web dependencies and Playwright Chromium first.
Recorded responses have no network fallback and are visibly labeled.
They exercise provider integration rather than actual Jev accuracy.
See the [Jev guide](jev-classification.md) for live smoke and benchmark commands.

## Live public-data demo

Stop conflicting web/API processes on ports 3000 and 8000 before starting:

```sh
docker compose -p arbbot-demo --env-file infra/demo.env up --build -d
```

This uses a separate project and database volume, with PostgreSQL on port 55433.
It enables Kalshi and Polymarket US, broad catalog traversal, and a monitoring budget of 20 contracts per venue.
Both supported US adapters use REST book polling; the browser never connects directly to exchanges.
The worker runs independently of page visibility, while current browser price queries refresh periodically and snapshot SSE refreshes result queries.
Freshness and unavailable states remain explicit, and a qualified result is not required for the demo to operate correctly.
Public endpoint access is subject to venue availability and authentication requirements; no private account connection is implemented.

```sh
docker compose -p arbbot-demo --env-file infra/demo.env logs --tail=50 worker
docker compose -p arbbot-demo --env-file infra/demo.env down
```

After installing frontend dependencies and Playwright Chromium, verify the supported live US pair with:

```sh
cd apps/web
node scripts/smoke-us-demo.mjs
```

This opt-in check depends on the recorded script's named Dodgers counterpart being discoverable with fresh books and the expected current source text.
A market closing or disappearing can make it unsuitable; failure is not permission to substitute fixtures for live data.
The script inspects paired prices, independent refreshes, comparison terms, and desktop/mobile layout.
Artifacts are written under `apps/web/test-results/us-demo-*.png`.

`apps/web/scripts/smoke-live.mjs` is the separate Kalshi/Polymarket International check and requires an explicitly configured International stack with WebSocket provenance.
It does not verify the default US demo.
Polymarket International streaming support must never be described as Polymarket US streaming support.

## Optional Jev provider

Set `OPENROUTER_API_KEY` in the backend environment to enable advice in a persistent live worker.
Keep it out of source control and `NEXT_PUBLIC_` variables.
Compose forwards the key only to backend containers.
Missing credentials leave deterministic discovery operational.
The default shared attempt limit is two per second, with no daily spending cap.
Use `ARBBOT_CLASSIFICATION_ENABLED=false` to disable classification.
Consult the [Jev guide](jev-classification.md) before running a live benchmark; recorded test responses do not establish live model quality.
