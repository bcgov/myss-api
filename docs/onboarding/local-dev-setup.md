# Local Development Setup

Get a working development environment from zero. The setup takes about 15 minutes on a clean machine.

## Prerequisites

| Tool | Required version | Notes |
|---|---|---|
| Python | 3.12 | Exact version — `python3.12 --version` |
| Node.js | 20 LTS | `node --version` |
| Docker | any recent | For PostgreSQL and Redis |
| Make | 3.8+ | Ships with macOS Xcode tools; `make --version` |

## Clone and Install

```bash
git clone <repo-url> myss
cd myss
```

### Backend (FastAPI)

```bash
cd myss-api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `[dev]` extra installs pytest, respx, fakeredis, ruff, and mypy in addition to the runtime dependencies listed in `pyproject.toml`.

### Frontend (SvelteKit)

```bash
cd myss-web
npm install
```

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

Create `myss-api/.env`:

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

# Siebel / ICM (set to real values or leave blank to stub)
ICM_BASE_URL=https://icm.example.gov.bc.ca
ICM_CLIENT_ID=myss-client
ICM_CLIENT_SECRET=
ICM_TOKEN_URL=https://icm.example.gov.bc.ca/oauth/token
```

Create `myss-web/.env`:

```dotenv
# Points to the FastAPI backend
PUBLIC_API_URL=http://localhost:8000

# Auth.js secret (any string for local dev)
AUTH_SECRET=local-dev-secret

# Keycloak (set to real values for OIDC-backed login)
AUTH_KEYCLOAK_ID=myss-web
AUTH_KEYCLOAK_SECRET=
AUTH_KEYCLOAK_ISSUER=https://keycloak.example.gov.bc.ca/realms/myss
```

`ENVIRONMENT=local` disables the startup check that enforces a secure `JWT_SECRET`, so `change-me-for-local-dev-only` is accepted in local development only.

## SQLite as a Quick Alternative

If you do not want to run Docker, the Alembic default URL in `myss-api/alembic.ini` is:

```
sqlalchemy.url = sqlite+aiosqlite:///./test.db
```

Set `DATABASE_URL=sqlite+aiosqlite:///./test.db` in your `.env` and skip the PostgreSQL container. SQLite is adequate for exploring the code and running tests, but some PostgreSQL-specific constraints will not be enforced.

## Run Alembic Migrations

From the repo root:

```bash
make migrate
```

This runs `alembic upgrade head` inside `myss-api/` using the `.venv` Python. On first run it creates all tables. Re-running is safe — Alembic tracks applied revisions.

## Start Both Services

Open two terminal windows.

**Terminal 1 — FastAPI:**

```bash
cd myss-api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — SvelteKit:**

```bash
cd myss-web
npm run dev
```

SvelteKit's dev server starts on port 5173 (Vite default). The API runs on port 8000.

## Verify

| Check | URL |
|---|---|
| API health | http://localhost:8000/health |
| Interactive API docs (Swagger UI) | http://localhost:8000/docs |
| OpenAPI JSON schema | http://localhost:8000/openapi.json |
| SvelteKit home page | http://localhost:5173 |

A `200 OK` from `/health` confirms the API started and connected to its dependencies. The Swagger UI at `/docs` lets you call any endpoint directly with a Bearer token — useful for exploring domain APIs without a frontend.

## Common Issues

**`ModuleNotFoundError: No module named 'app'`**
You are not inside the virtual environment or the package is not installed. Run `source .venv/bin/activate && pip install -e ".[dev]"` from `myss-api/`.

**`RuntimeError: JWT_SECRET must be set to a secure value`**
`ENVIRONMENT` is not set to `local` or `test`. Make sure your `.env` has `ENVIRONMENT=local`.

**`Connection refused` on port 5432 or 6379**
Docker containers are not running. Check `docker ps` and restart with the commands in the [Start Infrastructure](#start-infrastructure) section.

**`alembic: command not found`**
Use `make migrate` (which calls `.venv/bin/alembic`) rather than the system `alembic`.

**SvelteKit shows `CORS` errors in the browser console**
The `CORS_ALLOWED_ORIGINS` in `myss-api/.env` must include exactly the origin SvelteKit is serving from (default `http://localhost:5173`). Note: CORS applies to browser-originated requests. SvelteKit server-side fetches in `+page.server.ts` are not subject to CORS.

**Vitest or Playwright not found**
Run `npm install` inside `myss-web/`. Do not run `npm install` from the repo root — the web package is in its own directory.
