# Modifying ICM/Siebel REST API Connectivity

## When to use this guide

Use this guide when the Siebel REST API changes, new fields are needed in an existing operation, new Siebel operations are required, or error handling for a Siebel response needs updating.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)
- See also: [../reference/siebel-integration.md](../reference/siebel-integration.md) for the full reference

---

## ICM client architecture

All Siebel connectivity lives in `myss-api/app/services/icm/`:

```
myss-api/app/services/icm/
├── client.py           # ICMClient base class — OAuth2, retry, circuit breaker
├── deps.py             # lru_cache singletons (one per client type)
├── error_mapping.py    # Maps Siebel error codes to typed exceptions
├── exceptions.py       # Typed exception hierarchy
├── profile.py          # SiebelProfileClient — tombstone, PIN, profile (D1, D7, D10)
├── registration.py     # SiebelRegistrationClient — registration workflow
├── service_requests.py # SiebelSRClient — SR lifecycle (D2)
├── monthly_report.py   # SiebelMonthlyReportClient — monthly reports
├── notifications.py    # SiebelNotificationClient — banners, inbox (D4)
├── payment.py          # SiebelPaymentClient — payment info
├── employment_plans.py # SiebelEPClient — employment plans
├── attachments.py      # SiebelAttachmentClient — document uploads
├── admin.py            # SiebelAdminClient — worker/admin operations
└── account.py          # SiebelAccountClient — account management
```

### What `ICMClient` provides automatically

Every domain client inherits from `ICMClient` (`client.py`) and gets:

- **OAuth2 token management**: fetches a `client_credentials` token on first use, caches it, refreshes 60 seconds before expiry
- **Retry with exponential backoff**: 3 attempts, 1/2/4s wait, on 5xx responses and connection errors only; never retries on 4xx or typed `ICMError` subclasses
- **Circuit breaker**: opens after 5 consecutive failures (configurable via `circuit_failure_threshold`), 30-second recovery window (configurable via `circuit_recovery_timeout`). Raises `ICMServiceUnavailableError` while open.

You do not need to implement any of this in domain clients. Use only `self._get()`, `self._post()`, `self._put()`, and `self._delete()`.

---

## Step 1. Understand the existing client

Before modifying anything, read the relevant domain client. For example, `myss-api/app/services/icm/profile.py`:

```python
from app.services.icm.client import ICMClient

class SiebelProfileClient(ICMClient):
    """Siebel REST client for profile and tombstone operations. Covers: D1, D7, D10."""

    async def get_tombstone(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/tombstone")

    async def validate_pin(self, bceid_guid: str, pin: str) -> dict:
        return await self._post(f"/contacts/{bceid_guid}/validate-pin", json={"pin": pin})

    async def update_tombstone(self, bceid_guid: str, data: dict) -> dict:
        return await self._put(f"/contacts/{bceid_guid}/tombstone", json=data)

    async def get_profile(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/profile")

    async def link_profile(self, bceid_guid: str, link_data: dict) -> dict:
        return await self._post(f"/contacts/{bceid_guid}/link", json=link_data)

    async def has_newer_profile(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/has-newer-profile")
```

All methods are thin wrappers: construct the path, pass query params or JSON body, return the parsed response dict. The base class handles authentication and resilience.

---

## Step 2. Add or modify a method on the domain client

To add a new Siebel operation, add a new `async def` method on the appropriate client. To change an existing operation, modify the existing method.

Example — adding a new tombstone field fetch to `SiebelProfileClient`:

```python
async def get_contact_preferences(self, bceid_guid: str) -> dict:
    """Fetch communication preferences from Siebel. New in Siebel v2.4."""
    return await self._get(f"/contacts/{bceid_guid}/preferences")
```

Use keyword arguments for the httpx call:

```python
# Query params
await self._get("/endpoint", params={"key": "value"})

# JSON body
await self._post("/endpoint", json={"field": "value"})

# PUT with body
await self._put(f"/resource/{id}", json=update_data)

# DELETE
await self._delete(f"/resource/{id}")
```

Return type is always `dict` (the parsed JSON response body). If a Siebel response returns `null` or an empty body on success, handle that in the calling service layer, not in the client.

---

## Step 3. Register the client in `deps.py`

Every domain client is a singleton, cached with `@lru_cache(maxsize=1)` in `myss-api/app/services/icm/deps.py`:

```python
import os
from functools import lru_cache
from app.services.icm.profile import SiebelProfileClient

def _icm_kwargs() -> dict:
    return {
        "base_url": os.environ["ICM_BASE_URL"],
        "client_id": os.environ["ICM_CLIENT_ID"],
        "client_secret": os.environ["ICM_CLIENT_SECRET"],
        "token_url": os.environ["ICM_TOKEN_URL"],
    }

@lru_cache(maxsize=1)
def get_siebel_profile_client() -> SiebelProfileClient:
    return SiebelProfileClient(**_icm_kwargs())
```

For an entirely new client class (e.g. `SiebelWellnessClient`):

1. Create `myss-api/app/services/icm/wellness.py` following the pattern of `profile.py`
2. Add a getter function to `deps.py`:

```python
from app.services.icm.wellness import SiebelWellnessClient

@lru_cache(maxsize=1)
def get_siebel_wellness_client() -> SiebelWellnessClient:
    return SiebelWellnessClient(**_icm_kwargs())
```

3. Use `get_siebel_wellness_client()` in the router's dependency function, following the pattern in existing routers:

```python
from app.services.icm.deps import get_siebel_wellness_client

def _get_wellness_service() -> WellnessService:
    return WellnessService(client=get_siebel_wellness_client())
```

The `lru_cache` ensures that environment variables are only read once (at first call) and that a single `ICMClient` instance holds the OAuth2 token and circuit breaker state across the application lifetime.

---

## Step 4. Update error handling

### Adding a new error code

If Siebel introduces a new error code that this client may return, add:

**1. A new exception class** in `myss-api/app/services/icm/exceptions.py`:

```python
class ICMWellnessIneligibleError(ICMError):
    """Raised when Siebel reports the client is ineligible for wellness supplement."""
```

**2. A mapping entry** in `myss-api/app/services/icm/error_mapping.py`:

```python
_ERROR_MAP: dict[str, type[ICMError]] = {
    "ICM_ERR_NO_CASE": ICMCaseNotFoundError,
    "ICM_ERR_REVOKED": ICMAccessRevokedError,
    # ... existing ...
    "ICM_ERR_WELLNESS_INELIGIBLE": ICMWellnessIneligibleError,   # <-- add here
}
```

`map_icm_error()` is called automatically for every non-2xx response body. Any error code not in `_ERROR_MAP` falls back to the base `ICMError` class.

### Handling errors in the router

Catch typed exceptions in the router and map them to HTTP status codes:

```python
from app.services.icm.exceptions import ICMWellnessIneligibleError

@router.post("/wellness", ...)
async def submit_wellness(...):
    try:
        return await svc.submit_wellness(...)
    except ICMWellnessIneligibleError:
        raise HTTPException(status_code=403, detail="Not eligible for wellness supplement")
    except ICMServiceUnavailableError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
```

Never let `ICMError` subclasses propagate unhandled to the HTTP layer — FastAPI will return 500.

---

## Step 5. Mock the client in tests with respx

Use `respx` to intercept outbound httpx calls at the transport layer. You must mock both the OAuth2 token endpoint and the operation endpoint:

```python
import respx
import httpx
import pytest
from app.services.icm.profile import SiebelProfileClient

@pytest.fixture
def icm_config():
    return {
        "base_url": "https://icm.example.gov.bc.ca",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "token_url": "https://icm.example.gov.bc.ca/oauth/token",
    }

@respx.mock
async def test_get_contact_preferences(icm_config):
    respx.post(icm_config["token_url"]).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    respx.get(f"{icm_config['base_url']}/contacts/test-guid/preferences").mock(
        return_value=httpx.Response(200, json={"contact_method": "email"})
    )

    client = SiebelProfileClient(**icm_config)
    result = await client.get_contact_preferences("test-guid")
    assert result["contact_method"] == "email"
```

To test that a specific error code is mapped correctly:

```python
from app.services.icm.error_mapping import map_icm_error
from app.services.icm.exceptions import ICMWellnessIneligibleError

def test_map_wellness_ineligible_error():
    exc = map_icm_error({
        "errorCode": "ICM_ERR_WELLNESS_INELIGIBLE",
        "message": "Client not eligible"
    })
    assert isinstance(exc, ICMWellnessIneligibleError)
```

See `myss-api/tests/test_icm_client.py` for the full set of patterns including retry and circuit breaker tests.

---

## Step 6. Circuit breaker configuration reference

The circuit breaker parameters can be overridden per-client instance. In `ICMClient.__init__()`:

```python
def __init__(
    self,
    base_url: str,
    client_id: str,
    client_secret: str,
    token_url: str,
    circuit_failure_threshold: int = 5,      # open after this many consecutive failures
    circuit_recovery_timeout: int = 30,      # seconds before allowing a probe request
    _test_no_wait: bool = False,             # suppress retry sleep in tests
):
```

The defaults (5 failures, 30s recovery) apply to all production clients created via `deps.py`. Do not change the defaults without understanding the implications: a lower threshold opens the circuit faster (more protective, more disruptive); a longer recovery timeout means more downtime before the circuit self-heals.

States: `CLOSED` (normal) → `OPEN` (after 5 failures) → `HALF_OPEN` (one probe allowed after 30s) → `CLOSED` (probe succeeded).

In tests, use `circuit_failure_threshold=5, _test_no_wait=True` to test circuit breaker behaviour without retry waits.

---

## Verification

1. Add the new/modified method to the relevant domain client
2. `cd myss-api && pytest tests/test_icm_client.py tests/test_siebel_clients.py -x` — existing client tests still pass
3. Add a new test for the changed method using `respx` (see Step 5)
4. `pytest tests/ -x` — full test suite passes
5. Check that `error_mapping.py` handles all new error codes returned by the modified Siebel endpoint

---

## Common pitfalls

**Never access `ICMClient._token` directly.** Token management is internal. Use `self._get()` / `self._post()` which call `_ensure_token()` automatically. Accessing `_token` directly bypasses refresh logic.

**`lru_cache` caches the client forever.** In production the singleton is fine. In tests, `lru_cache` means the first call to `get_siebel_profile_client()` returns the same object for the entire test session. If you need a fresh client (e.g. to test circuit state), construct `SiebelProfileClient(**config)` directly in the test rather than using `deps.py`.

**All methods return `dict`.** If a Siebel endpoint returns an empty body (`204 No Content`) or a plain string, the `.json()` call in `ICMClient._call()` will raise. For 204 endpoints, override `_call()` in the domain client or handle the empty body explicitly.

**`respx.mock` is a decorator, not a context manager in all usages.** Use `@respx.mock` on the test function. If you need it as a context manager (e.g. in a fixture), use `with respx.mock:`. Do not mix the two styles in the same test.

**Error codes are case-sensitive.** `_ERROR_MAP` is keyed on the exact string from `response_body["errorCode"]`. `"ICM_ERR_NO_CASE"` and `"icm_err_no_case"` are different keys. Confirm the exact casing Siebel uses before adding a mapping.
