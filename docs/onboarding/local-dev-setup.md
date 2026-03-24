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

Create a `.env` file in the project root:

```dotenv
# Database
DATABASE_URL=postgresql+asyncpg://myss:myss@localhost:5432/myss

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=change-me-for-local-dev-only
ENVIRONMENT=local

# CORS (comma-separated; SvelteKit dev server runs on 5173)
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# AV webhook (shared secret for antivirus scan result callback)
AV_WEBHOOK_SECRET=local-dev-av-secret

# Siebel / ICM (leave blank for local dev — app starts without them in local mode)
ICM_BASE_URL=
ICM_CLIENT_ID=
ICM_CLIENT_SECRET=
ICM_TOKEN_URL=
```

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
