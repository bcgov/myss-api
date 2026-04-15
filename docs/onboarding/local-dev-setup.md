# Local Development Setup

Get a working myss-api development environment from zero.

## Prerequisites

| Tool | Required version | Notes |
|---|---|---|
| Python | 3.12+ | `python3 --version` |
| Docker | any recent | For PostgreSQL and Redis |

## Clone and Install

```bash
git clone <repo-url> myss-api
cd myss-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `[dev]` extra installs pytest, respx, fakeredis, ruff, and mypy in addition to the runtime dependencies listed in `pyproject.toml`.

## Start Infrastructure

The API requires PostgreSQL 16 and Redis 7. Run them in Docker:

```bash
# PostgreSQL
docker run -d \
  --name myss-postgres \
  -e POSTGRES_DB=myss \
  -e POSTGRES_USER=myss \
  -e POSTGRES_PASSWORD=myss \
  -p 5432:5432 \
  postgres:16

# Redis
docker run -d \
  --name myss-redis \
  -p 6379:6379 \
  redis:7
```

Verify both are up:

```bash
docker ps | grep -E "myss-postgres|myss-redis"
```

## Environment Variables

Copy the example env file and edit as needed:

    cp .env.example .env

The defaults work out of the box for SQLite + mock ICM; only change
values if you're pointing at a real Postgres, real Redis, or a real
Siebel environment.

`ENVIRONMENT=local` disables startup validation that enforces secure secrets and requires ICM connection details. In any other environment, `JWT_SECRET` must be a strong secret and all `ICM_*` variables must be set. See `app/config.py` for the full list of validated settings.

## SQLite as a Quick Alternative

If you do not want to run Docker, set `DATABASE_URL` to use SQLite:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./dev.db
```

Skip the PostgreSQL container. SQLite is adequate for exploring the code and running tests, but some PostgreSQL-specific constraints (JSON column behaviour, `NOW()` in raw SQL) will not be enforced.

You will still need Redis for admin session management and caching. If you want to skip Redis as well, the app will start but admin routes and caching will fail at runtime.

## Run Alembic Migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

On first run this creates all tables. Re-running is safe — Alembic tracks applied revisions.

## Seed Data & Mock Mode

### Seed the database

After running migrations, populate the database with test data:

```bash
python scripts/seed_db.py
```

This creates three test personas with realistic, relationship-consistent data across all tables:

| Persona | BCeID GUID | Case | Scenario |
|---|---|---|---|
| Alice Thompson | `alice-bceid-1001` | #100100 (Active) | Single client, 1 dependant, 2 SR drafts, clean attachment |
| Bob Chen | `bob-bceid-1002` | #100200 (Active) | Couple (spouse: Maria), PWD, employment plan pending signature |
| Carol Williams | `carol-bceid-1003` | #100300 (Closed) | Unlinked profile, edge-case testing |

The seeder also prints **JWT tokens** for each persona (valid 24 hours). Paste these into Swagger UI's **Authorize** dialog to call authenticated endpoints.

The command is idempotent — running it again skips existing records. To start fresh:

```bash
python scripts/seed_db.py --reset
```

### Mock ICM / Siebel mode

When `ENVIRONMENT=local` and `ICM_BASE_URL` is empty (the default in the `.env` template above), the API automatically uses **mock ICM clients** that return canned data instead of calling the real Siebel REST services. This means:

- All API endpoints return realistic data without VPN access
- No Siebel credentials or connectivity required
- You can exercise the full UI workflow locally

Mock mode is confirmed in the server logs at startup:

```
mock_icm_enabled=true msg="Using mock ICM clients — Siebel calls will return canned data"
```

To disable mock mode and use real Siebel (requires VPN), set `ICM_BASE_URL` to the actual endpoint in your `.env`.

## Start the API Server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Verify

| Check | URL |
|---|---|
| API health | http://localhost:8000/health |
| Interactive API docs (Swagger UI) | http://localhost:8000/docs |
| OpenAPI JSON schema | http://localhost:8000/openapi.json |

A `200 OK` from `/health` confirms the API started and connected to its dependencies. The Swagger UI at `/docs` lets you call any endpoint directly with a Bearer token — useful for exploring domain APIs without a frontend.

## Running Tests

```bash
# All tests
python -m pytest -v

# Specific test file
python -m pytest tests/test_auth.py -v

# With coverage
python -m pytest --cov=app

# Lint and type check
ruff check .
mypy app/
```

Tests use an in-memory SQLite database and fakeredis by default — no Docker containers needed to run the test suite.

## Common Issues

**`ModuleNotFoundError: No module named 'app'`**
You are not inside the virtual environment or the package is not installed. Run `source .venv/bin/activate && pip install -e ".[dev]"`.

**`RuntimeError: JWT_SECRET must be set to a secure value`**
`ENVIRONMENT` is not set to `local` or `test`. Make sure your `.env` has `ENVIRONMENT=local`.

**`Connection refused` on port 5432 or 6379**
Docker containers are not running. Check `docker ps` and restart with the commands in the [Start Infrastructure](#start-infrastructure) section.

**`alembic: command not found`**
Make sure you are in the virtual environment (`source .venv/bin/activate`). Alembic is installed as part of the `[dev]` extras.

**`KeyError: 'ICM_BASE_URL'` on first API request**
The Siebel client factories read `ICM_*` from the environment at first use. In local mode, set them to empty strings in `.env` — the app will start, but routes that call Siebel will fail with connection errors. This is expected for local development without VPN access to the ICM environment.
