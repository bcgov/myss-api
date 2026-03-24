# How to Write Tests in This Project

## When to use this guide

Use this guide when writing any new tests — unit, integration, or end-to-end — or when you need to understand the existing test conventions before modifying tests.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)

---

## Test stack at a glance

| Layer | Tool | Location |
|---|---|---|
| Backend unit + route tests | pytest + httpx | `myss-api/tests/` |
| Siebel HTTP mocking | respx | `myss-api/tests/` |
| Redis mocking | fakeredis | `myss-api/tests/` |
| Backend integration tests | pytest + unittest.mock | `myss-api/tests/integration/` |
| Domain unit tests | pytest | `myss-api/tests/domains/` |
| Frontend unit tests | Vitest + jsdom | `myss-web/src/**/*.test.ts` |
| E2E tests | Playwright | `myss-web/e2e/` |

---

## 1. Backend unit tests (pytest)

### Configuration

`asyncio_mode = "auto"` is set in `myss-api/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

This means **all `async def test_*` functions run automatically as async tests**. You do not need `@pytest.mark.asyncio` on individual tests. Do not add it — it is redundant and can cause warnings.

### The shared async client fixture

`myss-api/tests/conftest.py` provides a single shared fixture:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

Use this fixture for any test that sends HTTP requests to the FastAPI app. Tests do not need to start a real server.

### Generating auth tokens in tests

Routes require a JWT. Use the `make_token()` helper pattern found in the existing test files:

```python
import jwt as pyjwt
from datetime import datetime, timedelta, UTC

def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {
        "sub": "user1",
        "role": role,
        "bceid_guid": "test-bceid-guid",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")
```

Pass the token in the `Authorization` header:

```python
headers = {"Authorization": f"Bearer {make_token('CLIENT')}"}
response = await client.get("/service-requests", headers=headers)
```

For worker-only routes, use `make_token("WORKER")`.

### Overriding FastAPI dependencies

Override service layer dependencies with stubs using `app.dependency_overrides`. Always clean up in a `finally` block:

```python
from app.main import app
from app.routers.service_requests import _get_sr_service
from unittest.mock import AsyncMock, MagicMock

def _make_stub_service() -> ServiceRequestService:
    svc = MagicMock(spec=ServiceRequestService)
    svc.create_sr = AsyncMock(return_value=_STUB_DRAFT)
    return svc

@pytest.fixture(autouse=True)
def override_sr_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_sr_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_sr_service, None)
```

This pattern is used consistently in `test_sr_create.py`, `test_sr_submit.py`, `test_notifications.py`, etc.

---

## 2. Mocking Siebel with respx

`respx` intercepts `httpx` calls at the transport layer. Use it to mock Siebel REST responses without running a real server.

Basic pattern from `myss-api/tests/test_icm_client.py`:

```python
import pytest
import respx
import httpx
from app.services.icm.client import ICMClient

@pytest.fixture
def icm_config():
    return {
        "base_url": "https://icm.example.gov.bc.ca",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "token_url": "https://icm.example.gov.bc.ca/oauth/token",
    }

@respx.mock
async def test_token_refreshed_when_expired(icm_config):
    # Mock the OAuth2 token endpoint
    respx.post(icm_config["token_url"]).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    # Mock the target endpoint
    respx.get(f"{icm_config['base_url']}/test").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )

    client = ICMClient(**icm_config)
    await client._get("/test")
```

**Important:** ICMClient has retry logic (3 attempts on 5xx) and a circuit breaker. To suppress retry waits in tests, pass `_test_no_wait=True`:

```python
client = ICMClient(**icm_config, _test_no_wait=True)
```

To simulate retries, use a `side_effect` function:

```python
call_count = 0

def side_effect(request):
    nonlocal call_count
    call_count += 1
    if call_count < 3:
        return httpx.Response(500, json={"error": "server error"})
    return httpx.Response(200, json={"result": "ok"})

respx.get(f"{icm_config['base_url']}/test").mock(side_effect=side_effect)
```

To test circuit breaker behaviour, pass `circuit_failure_threshold=5`:

```python
client = ICMClient(**icm_config, circuit_failure_threshold=5, _test_no_wait=True)
# 5 failures open the circuit
for _ in range(5):
    try:
        await client._get("/test")
    except Exception:
        pass

with pytest.raises(ICMServiceUnavailableError):
    await client._get("/test")
```

---

## 3. Mocking Redis with fakeredis

`fakeredis` is listed as a dev dependency in `myss-api/pyproject.toml`. Use it when testing code that reads from or writes to Redis:

```python
import fakeredis.aioredis

@pytest.fixture
def mock_redis():
    return fakeredis.aioredis.FakeRedis()

async def test_banner_cache_sets_key(mock_redis):
    await mock_redis.setex("icm_cache:banners:CASE-001", 300, '{"banners":[]}')
    cached = await mock_redis.get("icm_cache:banners:CASE-001")
    assert cached is not None
```

For services that accept a redis client via constructor injection, pass the `FakeRedis` instance directly. For services that use a module-level redis connection, patch it with `monkeypatch.setattr`.

---

## 4. Backend integration tests

Integration tests in `myss-api/tests/integration/` mock at the Siebel client boundary and run the real service logic end-to-end. The `AsyncSession` is also mocked since there is no test database.

Pattern from `myss-api/tests/integration/test_sr_flow.py`:

```python
async def test_full_sr_lifecycle():
    client = _stub_siebel_client()   # AsyncMock(spec=SiebelSRClient)
    session = _mock_session()        # in-memory dict simulating sr_drafts table
    svc = ServiceRequestService(sr_client=client, session=session)

    app.dependency_overrides[_get_sr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Create SR
            r = await ac.post("/service-requests", json={"sr_type": "ASSIST"}, headers=headers)
            assert r.status_code == 201
            sr_id = r.json()["sr_id"]

            # 2. Save draft
            r = await ac.put(
                f"/service-requests/{sr_id}/form",
                json={"answers": {"reason": "Test"}, "page_index": 0},
                headers=headers,
            )
            assert r.status_code == 200

            # 3. Submit
            r = await ac.post(
                f"/service-requests/{sr_id}/submit",
                json={"pin": "1234", "declaration_accepted": True},
                headers=headers,
            )
            assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(_get_sr_service, None)
```

The `_mock_session()` helper in that file implements an in-memory `sr_drafts` dict that behaves like the real database for INSERT, UPDATE, SELECT, and DELETE operations.

For other domains, follow the same pattern: mock the Siebel client with `AsyncMock(spec=<ClientClass>)`, mock the session if needed, inject both through a dependency override.

---

## 5. Frontend unit tests (Vitest)

Vitest is configured in `myss-web/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
    plugins: [sveltekit()],
    test: {
        environment: 'jsdom',
        globals: true,
        include: ['src/**/*.{test,spec}.{js,ts}'],
    },
});
```

Tests run in jsdom and use the Svelte compiler via the SvelteKit Vite plugin. `globals: true` means `describe`, `it`, `expect`, `vi` are available without imports.

To test a utility function:

```typescript
// src/lib/utils/format.test.ts
import { formatSRType } from './format';

describe('formatSRType', () => {
    it('converts CRISIS_FOOD to Crisis Food', () => {
        expect(formatSRType('CRISIS_FOOD')).toBe('Crisis Food');
    });
});
```

To test a Svelte component, use `@testing-library/svelte`:

```typescript
import { render, screen } from '@testing-library/svelte';
import MyComponent from './MyComponent.svelte';

it('renders heading', () => {
    render(MyComponent, { props: { title: 'Hello' } });
    expect(screen.getByRole('heading', { name: 'Hello' })).toBeInTheDocument();
});
```

Run tests with:

```bash
cd myss-web
npm run test        # watch mode
npm run test -- run # run once (CI mode)
```

---

## 6. E2E tests (Playwright)

Playwright tests are in `myss-web/e2e/`. Configuration is in `myss-web/playwright.config.ts`:

```typescript
export default defineConfig({
    testDir: './e2e',
    use: {
        baseURL: 'http://localhost:5173',
    },
    webServer: {
        command: 'npm run dev',
        port: 5173,
        reuseExistingServer: !process.env.CI,
    },
});
```

Playwright starts the dev server automatically. Tests use `page` from `@playwright/test`:

```typescript
// e2e/registration.test.ts
import { test, expect } from '@playwright/test';

test.describe('Registration wizard', () => {
    test('step 1 page loads with account type radio buttons', async ({ page }) => {
        await page.goto('/registration');
        await expect(page.getByRole('heading', { name: 'Create an Account' })).toBeVisible();
        await expect(page.getByText('Step 1 of 5')).toBeVisible();
    });
});
```

Run E2E tests with:

```bash
cd myss-web
npx playwright test
npx playwright test --ui   # interactive mode
```

E2E tests cover user-visible flows, not implementation details. Target scenarios a real user would exercise: completing multi-step forms, error states, navigation.

---

## 7. Where files go — mirror the source structure

Tests mirror the source file structure:

```
myss-api/
├── app/
│   ├── domains/service_requests/service.py      # source
│   └── services/icm/client.py
├── tests/
│   ├── conftest.py
│   ├── domains/
│   │   └── registration/
│   │       └── test_service.py                  # unit test for registration service
│   ├── integration/
│   │   └── test_sr_flow.py                      # integration test
│   └── test_icm_client.py                       # unit test for ICM client
```

For a new domain at `app/domains/my_feature/service.py`, add unit tests at `tests/domains/my_feature/test_service.py`. For a new Siebel client at `app/services/icm/my_feature.py`, add tests at `tests/test_siebel_my_feature.py` (following the pattern of `test_siebel_clients.py`).

Frontend tests go in the same directory as the source file:

```
myss-web/src/lib/utils/format.ts
myss-web/src/lib/utils/format.test.ts
```

---

## 8. CI expectations

All of the following must pass before a PR can merge:

- `cd myss-api && pytest tests/ -x` — all backend tests
- `cd myss-web && npm run test -- run` — all Vitest tests

Ruff linting: `cd myss-api && ruff check .`
Mypy type checking: `cd myss-api && mypy app/`

**Playwright E2E tests do NOT currently run in CI.** They are run manually by
developers or as part of the deploy pipeline (against a deployed environment).
To run them locally:

```bash
cd myss-web
npx playwright test
npx playwright test --ui   # interactive mode
```

---

## 9. Common pitfalls

**Not cleaning up `dependency_overrides`.** If a test overrides a FastAPI dependency and does not clean up, subsequent tests in the same session inherit the override. Always use `app.dependency_overrides.pop(key, None)` in a `finally` block or `autouse` fixture teardown.

**Forgetting `_test_no_wait=True` on `ICMClient`.** The client uses exponential backoff (1/2/4s). Without `_test_no_wait=True`, retry tests sleep for several seconds. Always pass this flag when constructing `ICMClient` in tests.

**`@pytest.mark.asyncio` is not needed.** With `asyncio_mode = "auto"`, all async test functions are automatically awaited. Adding `@pytest.mark.asyncio` is harmless but unnecessary and inconsistent with existing tests.

**Using `AsyncMock` for non-async methods.** `MagicMock(spec=ServiceRequestService)` creates a regular mock. Use `AsyncMock(return_value=...)` for async methods, and plain `MagicMock(return_value=...)` for sync methods. Mixing them causes `TypeError: object MagicMock can't be used in 'await' expression`.

**Over-mocking.** Integration tests in `tests/integration/` are most valuable when they run through real business logic. Mock only at the external boundaries: Siebel clients and the database session. Avoid mocking individual service methods in integration tests — that defeats their purpose.

**Flaky async tests due to shared state.** `ICMClient` instances have an internal circuit breaker. If a test triggers the circuit open state and does not clean up (by constructing a new client), subsequent tests using the same client instance will fail with `ICMServiceUnavailableError`. Always construct a new client instance per test.
