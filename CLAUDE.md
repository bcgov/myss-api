# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

myss-api is a FastAPI backend (Python 3.12) for BC Government's MySelfServe income assistance self-service portal. It integrates with Siebel/ICM REST services for backend operations and serves a SvelteKit frontend (separate repo: myss-web).

## Build and Development Commands

```bash
# Create venv and install
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run development server
uvicorn app.main:app --reload --port 8000

# Run all tests
python -m pytest -v

# Lint and type check
ruff check .
mypy app/

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture

### Domain-Driven Vertical Slices

Each domain in `app/domains/` owns its models, schemas, service, and Siebel client:
- `account/` — profile info, contact updates, case members
- `attachments/` — upload, AV scan, download
- `eligibility/` — anonymous eligibility estimator (pure calculation)
- `employment_plans/` — EP signing
- `monthly_reports/` — SD81 monthly reports
- `notifications/` — banners + inbox messages
- `payment/` — payment info, cheque schedule, T5007
- `registration/` — multi-step registration wizard
- `service_requests/` — full SR lifecycle

### Three-Layer Pattern

1. **Routers** (`app/routers/`) — HTTP parsing, auth enforcement, error translation
2. **Domain Services** (`app/domains/*/service.py`) — business logic orchestration
3. **Siebel Clients** (`app/services/icm/`) — thin REST wrappers extending `ICMClient`

### Authentication

- JWT Bearer tokens (HS256)
- `get_current_user` dependency decodes and validates tokens
- `require_role(UserRole.CLIENT|WORKER|ADMIN)` enforces role-based access
- Worker routes additionally require `idir_username` in JWT claims

### Key Infrastructure

- **ICMClient** (`app/services/icm/client.py`) — base class with OAuth2 token management, retry with exponential backoff, async circuit breaker
- **RedisSessionStore** (`app/dependencies/session_store.py`) — generic Redis-backed session store for admin flows
- **Global exception handlers** (`app/exception_handlers.py`) — ICMServiceUnavailableError → 503, PINValidationError → 403, etc.
- **Centralized config** (`app/config.py`) — Pydantic BaseSettings validates all env vars at startup

### Database

- PostgreSQL via SQLAlchemy async
- Alembic for migrations (hand-written in `alembic/versions/`)
- SQLModel ORM tables in `app/models/`
- The `sr_drafts` table uses string PKs from Siebel; other tables use UUID PKs

### WCF/Siebel Integration

All external data access goes through the `app/services/icm/` Siebel REST clients. The `ICMClient` base class handles:
- OAuth2 client credentials with proactive token refresh
- Retry (3 attempts, exponential backoff, 5xx only)
- Circuit breaker (5 failures → open, 30s recovery)

## Code Conventions

- **Routers**: Suffix with `_router`, grouped by domain
- **Services**: Plain classes, dependencies injected via `__init__`
- **Models**: SQLModel for ORM, Pydantic BaseModel for DTOs
- **Tests**: pytest-asyncio, httpx AsyncClient, fakeredis, respx for HTTP mocking
- **Logging**: structlog with JSON rendering
- **Config**: All via environment variables, validated in `app/config.py`

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./dev.db` | Database connection |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection |
| `JWT_SECRET` | Prod only | `change-me-in-production` | JWT signing secret |
| `ENVIRONMENT` | No | `local` | Environment name. `local` or `test` with empty `ICM_BASE_URL` activates mock ICM clients. |
| `ICM_BASE_URL` | Prod only | — | Siebel REST base URL. Leave empty in local/test to use mock ICM. |
| `ICM_CLIENT_ID` | Prod only | — | Siebel OAuth client ID |
| `ICM_CLIENT_SECRET` | Prod only | — | Siebel OAuth client secret |
| `ICM_TOKEN_URL` | Prod only | — | Siebel OAuth token endpoint |
| `AV_WEBHOOK_SECRET` | Yes | — | Shared secret for AV scan webhook |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:5173,...` | Comma-separated CORS origins |
| `SEED_TOKEN_TTL_DAYS` | No | `1` | JWT expiry (days) for tokens produced by `scripts/seed_db.py`. Test-env seed Job uses `90`. |
