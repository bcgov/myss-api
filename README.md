# myss-api

FastAPI backend for the BC Government MySelfServe income assistance self-service portal.

## Tech Stack

- **Python 3.12** + **FastAPI** — async web framework
- **SQLAlchemy async** + **Alembic** — database ORM and migrations
- **PostgreSQL** — primary data store
- **Redis** — session cache, rate limiting, Celery broker
- **Celery** — background task processing (email notifications)
- **httpx** — async HTTP client for Siebel/ICM REST integration
- **PyJWT** — JWT authentication (BCeID for clients, IDIR for workers)

## Quick Start

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs` (Swagger UI).

## Testing

```bash
# Run all tests
python -m pytest -v

# Run with coverage
python -m pytest --cov=app

# Lint and type check
ruff check .
mypy app/
```

## Project Structure

```
app/
├── auth/           # JWT authentication and role-based authorization
├── cache/          # Redis client and cache key definitions
├── config.py       # Centralized Pydantic BaseSettings configuration
├── db/             # SQLAlchemy async engine and session
├── dependencies/   # FastAPI dependency injection (session store, role checks)
├── domains/        # Business domains (vertical slices)
│   ├── account/
│   ├── attachments/
│   ├── eligibility/
│   ├── employment_plans/
│   ├── monthly_reports/
│   ├── notifications/
│   ├── payment/
│   ├── registration/
│   └── service_requests/
├── exception_handlers.py  # Global FastAPI exception handlers
├── middleware/      # ASGI middleware (audit trail)
├── models/          # SQLModel ORM table definitions
├── routers/         # FastAPI route handlers
├── services/        # External service clients (Siebel/ICM)
│   └── icm/         # ICM REST client with circuit breaker + retry
└── workers/         # Celery background tasks
```

## Deployment

Container image built from `Dockerfile`. Deployed to OpenShift via manifests in `openshift/`.

See `docs/ops/` for deployment runbooks and infrastructure setup guides.

## Related Repository

- **myss-web** — SvelteKit frontend ([../myss-web](../myss-web))
