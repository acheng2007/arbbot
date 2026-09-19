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
