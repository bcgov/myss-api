# Adding a New API Endpoint

## When to use this guide

Use this guide when new backend functionality is needed — a new resource, a new action on an existing resource, or a new admin-facing operation.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)
- The feature's domain logic is either already in `app/domains/` or you know where it will live

---

## Steps

### 1. Create or extend a router in `app/routers/`

Each domain has its own router file. The pattern from `myss-api/app/routers/service_requests.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.db.session import get_session
from app.domains.your_domain.service import YourDomainService

router = APIRouter(prefix="/your-resource", tags=["your-resource"])
```

- `prefix` becomes the URL path segment (e.g. `/your-resource`)
- `tags` groups the endpoints in the interactive docs at `/docs`

If the resource is genuinely new, create `app/routers/your_resource.py`. If you are extending an existing resource (e.g. adding a new action to service requests), add the handler to the existing file.

### 2. Define Pydantic request and response models

Put models in `app/domains/your_domain/models.py`. Use Pydantic `BaseModel` for request/response shapes (not SQLModel — those are for DB tables):

```python
from pydantic import BaseModel

class YourCreateRequest(BaseModel):
    name: str
    value: int

class YourCreateResponse(BaseModel):
    id: str
    name: str
    value: int
    created_at: str
```

Keep request models separate from response models. Never reuse a DB model directly as a response model.

### 3. Wire the database session with a service factory

The pattern from `service_requests.py` uses a local factory function so that `Depends()` works without circular imports:

```python
def _get_your_service(session: AsyncSession = Depends(get_session)) -> YourDomainService:
    return YourDomainService(session=session)
```

`get_session` yields an `AsyncSession` from `app/db/session.py`. The session is scoped to the request and committed/rolled back automatically.

### 4. Add auth with `require_role()`

Every endpoint that touches user data must declare a `user` parameter using `Depends(require_role(...))`. The `require_role()` factory from `app/auth/dependencies.py` enforces the role and returns a populated `UserContext`:

```python
@router.get("", response_model=YourListResponse)
async def list_your_resource(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: YourDomainService = Depends(_get_your_service),
) -> YourListResponse:
    return await svc.list(user_id=user.user_id)
```

Available roles (from `app/auth/models.py`):

| Role | Who | Notes |
|---|---|---|
| `UserRole.CLIENT` | BCeID-authenticated income assistance clients | Most endpoints |
| `UserRole.WORKER` | IDIR-authenticated ministry workers | Admin operations; ADMIN role also accepted |
| `UserRole.ADMIN` | System administrators | Elevated access |

Worker→Admin inheritance: `require_role(UserRole.WORKER)` also accepts `ADMIN` callers. This logic is built into `require_role()` — you do not need to handle it yourself.

### 5. Write the handler with correct HTTP semantics

```python
@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ResourceService = Depends(_get_resource_service),
) -> ResourceResponse:
    """Fetch a resource by ID.

    ICM errors (service unavailable, upstream errors) are translated to
    HTTP responses by the global exception handlers in
    app/exception_handlers.py. Only catch domain-specific errors in the
    router when a non-default status code or response shape is needed.
    """
    return await svc.get_resource(user.user_id, resource_id)
```

Standard HTTP codes used in this codebase:

| Code | Meaning | When |
|---|---|---|
| 200 | OK | GET returning data |
| 201 | Created | POST that creates a resource |
| 204 | No Content | DELETE / withdraw with no response body |
| 400 | Bad Request | Validation failure, bad input |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Wrong role, PIN mismatch |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Duplicate, already-withdrawn resource |
| 503 | Service Unavailable | Siebel/ICM unreachable |

### 6. Register the router in `app/main.py`

Open `myss-api/app/main.py` and add two things:

**Import:**
```python
from app.routers.your_resource import router as your_resource_router
```

**Register** (add alongside the existing `app.include_router()` calls):
```python
app.include_router(your_resource_router)
```

The existing registrations in `main.py` for reference:
```python
app.include_router(sr_router)
app.include_router(mr_router)
app.include_router(notifications_router)
app.include_router(payment_router)
app.include_router(ep_router)
```

Order does not matter for correctness, but keep related routers grouped.

### 7. Write tests

Create `myss-api/tests/test_your_resource.py`. Use `httpx.AsyncClient` with `ASGITransport` and a real JWT, the same pattern used in `tests/test_auth.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
import jwt as pyjwt
from datetime import datetime, timedelta, UTC
from app.main import app


def make_token(role: str = "CLIENT", secret: str = "test-secret") -> str:
    payload = {
        "sub": "test-user-id",
        "role": role,
        "bceid_guid": "test-bceid-guid",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
async def client(monkeypatch):
    import app.auth.dependencies as deps
    monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def test_list_returns_200_for_client(client):
    token = make_token("CLIENT")
    response = await client.get(
        "/your-resource",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

async def test_list_returns_401_without_token(client):
    response = await client.get("/your-resource")
    assert response.status_code == 401

async def test_list_returns_403_for_wrong_role(client):
    token = make_token("WORKER")
    response = await client.get(
        "/your-resource",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
```

---

## Verification

```bash
# Run the test suite
cd myss-api && .venv/bin/python -m pytest tests/test_your_resource.py -v
# or: make test-api

# Start the dev server and check interactive docs
# See docs/onboarding/local-dev-setup.md for full startup instructions.
cd myss-api && uvicorn app.main:app --reload --port 8000
# Then open: http://localhost:8000/docs
# Your router's prefix and endpoints will appear under the tag you set.

# In a separate terminal, start the frontend if needed:
cd myss-web && npm run dev

# Test with curl using a JWT (replace TOKEN with a valid token):
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/your-resource
```

---

## Common pitfalls

**Forgetting to register the router in `main.py`**
The endpoint exists in code but returns 404. Every new router file must be imported and passed to `app.include_router()` in `main.py`. This is the most common mistake.

**Missing auth dependency**
Omitting `Depends(require_role(...))` leaves the endpoint publicly accessible. FastAPI will not warn you. Every endpoint that touches user data must have the dependency declared.

**Wrong HTTP status codes**
FastAPI defaults to 200. Use `status_code=201` on `@router.post` for resource creation and `status_code=204` for no-body responses. Returning 200 for a created resource is incorrect and breaks some clients.

**Reusing DB models as response models**
SQLModel table models expose internal fields (foreign keys, internal IDs) and cause serialization issues. Always define separate Pydantic response models in `app/domains/your_domain/models.py`.

### Error Handling

Global exception handlers in `app/exception_handlers.py` translate domain
exceptions to HTTP responses so routers stay thin:

| Exception | HTTP Status | Notes |
|-----------|-------------|-------|
| `ICMServiceUnavailableError` | 503 | Siebel unreachable or circuit breaker open |
| `ICMActiveSRConflictError` | 409 | Active SR of same type already exists |
| `ICMSRAlreadyWithdrawnError` | 409 | SR already in withdrawn state |
| `PINValidationError` | 403 | PIN check failed |
| `ReportingPeriodClosedError` | 422 | Monthly-report period has closed |
| `ICMError` (base class) | 502 | Fallthrough for any unmapped ICM subclass |

Do **not** wrap service calls in `try/except ICMServiceUnavailableError`
in routers — the global handler already catches it. Only add a manual
try/except when you need a non-default status or a custom response body
for a specific domain condition.
