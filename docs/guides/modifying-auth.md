# Modifying Authentication and Authorization

## When to use this guide

Use this guide when you need to add a new role, add a permission check to an existing endpoint, change what an existing role can access, or understand how the token flow works end-to-end.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)

---

## Steps

### 1. Understand the auth structure

Auth lives in two files in `myss-api/app/auth/`:

- `models.py` — data structures: `UserRole` enum and `UserContext` dataclass
- `dependencies.py` — FastAPI dependency functions: `get_current_user()` and `require_role()`

The full token flow:

```
Auth.js (SvelteKit) mints a signed JWT
    → SvelteKit sends "Authorization: Bearer <token>" header to FastAPI
    → FastAPI decodes and validates the JWT in get_current_user()
    → require_role() checks the role claim against the required role
    → The UserContext is injected into the route handler via Depends()
```

The JWT is signed with `JWT_SECRET` (env var). Auth.js on the SvelteKit side and FastAPI on the API side must share the same secret. In production this is a per-environment secret stored in OpenShift Secrets.

### 2. The `UserRole` enum and `UserContext` model

The complete `myss-api/app/auth/models.py`:

```python
from enum import Enum
from pydantic import BaseModel


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    WORKER = "WORKER"
    ADMIN = "ADMIN"


class UserContext(BaseModel):
    user_id: str
    role: UserRole
    bceid_guid: str | None = None
    idir_username: str | None = None
```

`UserRole` is a `str` enum so that its values serialise cleanly to/from JSON and JWT claims. `UserContext` is a Pydantic model that holds the decoded token claims for one request.

**Adding a new role**: add a new member to `UserRole`. Choose a value string that matches what Auth.js will put in the `role` JWT claim. You will also need to update Auth.js to assign the role at sign-in, and update any `require_role()` calls that need to accept the new role.

### 3. The `require_role()` factory and the WORKER→ADMIN inheritance rule

The complete `myss-api/app/auth/dependencies.py`:

```python
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt as pyjwt
from jwt.exceptions import PyJWTError
from app.auth.models import UserContext, UserRole

security = HTTPBearer(auto_error=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"

_INSECURE_DEFAULTS = {"change-me-in-production", "secret", ""}


def validate_jwt_config() -> None:
    """Called at startup. Raises RuntimeError if JWT_SECRET is insecure in non-local environments."""
    if ENVIRONMENT not in ("local", "test") and JWT_SECRET in _INSECURE_DEFAULTS:
        raise RuntimeError(
            f"JWT_SECRET must be set to a secure value in environment '{ENVIRONMENT}'. "
            "Set the JWT_SECRET environment variable."
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    import app.auth.dependencies as _self
    secret = _self.JWT_SECRET
    try:
        payload = pyjwt.decode(
            credentials.credentials,
            secret,
            algorithms=[JWT_ALGORITHM],
        )
        return UserContext(
            user_id=payload["sub"],
            role=UserRole(payload["role"]),
            bceid_guid=payload.get("bceid_guid"),
            idir_username=payload.get("idir_username"),
        )
    except (PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_role(required_role: UserRole):
    async def _require(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role != required_role and not (
            required_role == UserRole.WORKER and user.role == UserRole.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required; caller has '{user.role}'",
            )
        return user

    return _require
```

**Key behaviour to note:**

The `require_role()` factory contains a WORKER→ADMIN inheritance rule:

```python
if user.role != required_role and not (
    required_role == UserRole.WORKER and user.role == UserRole.ADMIN
):
    raise HTTPException(status_code=403, ...)
```

This means: if the endpoint requires `WORKER`, an `ADMIN` caller is also accepted. Any other role mismatch raises 403. This is the only inheritance rule — `CLIENT` routes do not accept `WORKER` callers, and `ADMIN` routes do not accept `WORKER` callers.

**`JWT_SECRET` is read at call-time** (via `import app.auth.dependencies as _self; secret = _self.JWT_SECRET`) rather than at module import time. This makes `monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")` work correctly in tests.

### 4. Applying auth to routes

Every route handler that touches user data must declare a `user` parameter:

```python
from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole

@router.get("/my-resource")
async def get_my_resource(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MyService = Depends(_get_svc),
):
    return await svc.get(user_id=user.user_id)
```

For worker-only endpoints:

```python
@router.get("/admin/report")
async def admin_report(
    user: UserContext = Depends(require_role(UserRole.WORKER)),
    svc: AdminService = Depends(_get_svc),
):
    # ADMIN callers are also accepted (WORKER→ADMIN inheritance)
    return await svc.generate_report()
```

For endpoints that need the user identity regardless of role (rare — for public-ish endpoints that behave differently when authenticated):

```python
from app.auth.dependencies import get_current_user

@router.get("/public-with-optional-auth")
async def public_endpoint(
    user: UserContext = Depends(get_current_user),  # raises 401 if no token
):
    ...
```

### 5. Understanding the full token flow

```
1. User signs in via Auth.js (BCeID for clients, IDIR for workers)
2. Auth.js calls its JWT callback; the role is set based on the provider:
      BCeID sign-in  → role = "CLIENT"
      IDIR sign-in   → role = "WORKER" or "ADMIN" based on AD group
3. Auth.js signs the JWT with JWT_SECRET and sets exp = now + session duration
4. SvelteKit sends the token as a Bearer header to every API request
5. FastAPI's HTTPBearer extracts the token from the Authorization header
6. get_current_user() decodes the JWT with pyjwt using the same JWT_SECRET
7. require_role() checks the role claim
8. The UserContext is injected into the route handler
```

JWT claims decoded from the token:

| Claim | Type | Description |
|---|---|---|
| `sub` | string | User's unique ID (maps to `user_id`) |
| `role` | string | One of: `CLIENT`, `WORKER`, `ADMIN` |
| `bceid_guid` | string or null | BCeID GUID for client users |
| `idir_username` | string or null | IDIR username for worker/admin users |
| `exp` | integer | Unix timestamp expiry |

### 6. Test patterns from `tests/test_auth.py`

The test file shows three patterns that cover the auth contract:

```python
import pytest
from httpx import AsyncClient, ASGITransport
import jwt as pyjwt
from datetime import datetime, timedelta, UTC
from app.main import app


def make_token(role: str, secret: str = "test-secret", algorithm: str = "HS256") -> str:
    payload = {
        "sub": "test-user-id",
        "role": role,
        "bceid_guid": "test-bceid-guid",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
async def authed_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# Pattern 1: No token → 401
async def test_missing_token_returns_401(authed_client):
    response = await authed_client.get("/api/protected-test")
    assert response.status_code == 401


# Pattern 2: Wrong role → 403
async def test_client_jwt_rejected_by_worker_route(authed_client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    import app.auth.dependencies as deps
    monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")
    token = make_token("CLIENT")
    response = await authed_client.get(
        "/api/worker-only-test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# Pattern 3: Correct role → accepted
async def test_worker_jwt_accepted_by_worker_route(authed_client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    import app.auth.dependencies as deps
    monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")
    token = make_token("WORKER")
    response = await authed_client.get(
        "/api/worker-only-test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code != 401
    assert response.status_code != 403
```

**Required test coverage for any new auth change:**

1. No token → 401
2. Expired token → 401
3. Wrong role → 403
4. Correct role → 200 (or the expected success code)
5. WORKER→ADMIN inheritance: if an endpoint requires WORKER, verify ADMIN is also accepted

To test the ADMIN inheritance:

```python
async def test_admin_accepted_on_worker_route(authed_client, monkeypatch):
    import app.auth.dependencies as deps
    monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")
    token = make_token("ADMIN")
    response = await authed_client.get(
        "/api/worker-only-test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code not in (401, 403)
```

---

## Verification

```bash
cd myss-api

# Run the full test suite
make test

# Run only auth tests
cd myss-api && .venv/bin/python -m pytest tests/test_auth.py -v

# Alternatively, use the Makefile shortcut
make test-api
```

---

## Common pitfalls

**Unprotected routes**
FastAPI will not warn you if a route handler lacks a `Depends(require_role(...))` parameter. Any route without it is publicly accessible. Audit new routers before merging to confirm every handler has the correct dependency.

**`JWT_SECRET` mismatch between environments**
If Auth.js signs tokens with a different `JWT_SECRET` than FastAPI uses for verification, every request will return 401. This is the first thing to check when auth stops working in a new environment. Verify that both the SvelteKit secret and the API secret come from the same OpenShift Secret object.

**Insecure default secret in non-local environments**
`validate_jwt_config()` is called at startup (in `app/main.py`'s lifespan context) and raises `RuntimeError` if `JWT_SECRET` is set to `"change-me-in-production"`, `"secret"`, or `""` in any environment other than `local` or `test`. If the API pod fails to start, check the pod logs for this error.

**Module-level `JWT_SECRET` caching in tests**
The `JWT_SECRET` variable is read at module import time in `dependencies.py`. To override it in tests, always use both `monkeypatch.setenv("JWT_SECRET", "test-secret")` and `monkeypatch.setattr(deps, "JWT_SECRET", "test-secret")`. The `setattr` patch is what actually takes effect at call time.

**Adding a role without updating Auth.js**
`UserRole` in `app/auth/models.py` and the role assignment in Auth.js must be kept in sync. If FastAPI knows about a new role but Auth.js never assigns it, no tokens will ever have that role value. If Auth.js assigns a role string that does not match a `UserRole` enum member, `get_current_user()` raises a `ValueError` and the user gets a 401.
