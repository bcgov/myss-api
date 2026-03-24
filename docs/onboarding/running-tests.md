# Running Tests

This document covers all test layers, how to run them locally, and what CI requires before a PR can merge.

## Quick Reference

| Command | What it runs |
|---|---|
| `make test` | Backend pytest + frontend Vitest (in sequence) |
| `make test-api` | Backend pytest only |
| `make test-web` | Frontend Vitest only |
| `make test-e2e` | Playwright end-to-end tests |
| `make lint-api` | ruff check + mypy (backend) |
| `make lint-web` | svelte-check (frontend TypeScript) |

All `make` commands must be run from the repo root. They use `.venv/bin/python` and `npm` from their respective subdirectories — you do not need to `cd` first.

## Backend Tests (pytest)

**Location:** `myss-api/tests/`

**Run:**

```bash
make test-api
# equivalent to: cd myss-api && .venv/bin/python -m pytest
```

For more verbose output during development:

```bash
cd myss-api && .venv/bin/python -m pytest -v --tb=short
```

### pytest configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`asyncio_mode = "auto"` means all `async def test_*` functions run under an event loop automatically — no `@pytest.mark.asyncio` decorator needed.

### Fixtures (`tests/conftest.py`)

The root conftest provides a single fixture:

```python
@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

`client` is an `httpx.AsyncClient` wired to the FastAPI ASGI app in-process. No real network calls are made. Use it in every test that exercises an HTTP endpoint:

```python
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
```

### Mocking patterns

**Siebel (ICM) calls — `respx`**

`respx` intercepts `httpx` calls at the transport level. Use it to stub Siebel REST responses without standing up a real ICM instance:

```python
import respx
import httpx

@respx.mock
async def test_get_tombstone(client):
    respx.get("https://icm.example.gov.bc.ca/contacts/abc123/tombstone").mock(
        return_value=httpx.Response(200, json={"name": "Test User"})
    )
    response = await client.get("/api/profile/tombstone", headers={"Authorization": "Bearer ..."})
    assert response.status_code == 200
```

**Redis — `fakeredis`**

`fakeredis` provides an in-memory Redis implementation compatible with the `redis-py` async API. Patch the Redis client in the fixture or test to avoid needing a real Redis instance:

```python
import fakeredis.aioredis as fakeredis

@pytest.fixture
async def fake_redis():
    return fakeredis.FakeRedis()
```

Both `respx` and `fakeredis` are installed as part of the `[dev]` extras in `pyproject.toml`.

### Lint and type checking

```bash
make lint-api
# equivalent to: cd myss-api && .venv/bin/ruff check . && .venv/bin/mypy app/
```

- **ruff:** line length 100, target Python 3.12 (configured in `pyproject.toml`)
- **mypy:** strict mode, `ignore_missing_imports = true`

Fix ruff errors automatically with `ruff check . --fix`. mypy errors must be resolved manually.

## Frontend Unit Tests (Vitest)

**Location:** `myss-web/src/` — test files co-located with source files (`*.test.ts`)

**Run:**

```bash
make test-web
# equivalent to: cd myss-web && npm test
# which runs: vitest run
```

For watch mode during development:

```bash
cd myss-web && npm run test:watch
```

### Environment

Vitest uses `jsdom` (version 29.x, declared in `devDependencies`) as the DOM environment. This means browser globals like `document`, `window`, and `fetch` are available in tests without a real browser.

Tests use `@testing-library/svelte` for rendering components and asserting on the DOM. Avoid testing internal component state — test what a user would see or interact with.

### Frontend type checking

```bash
make lint-web
# equivalent to: cd myss-web && npm run check
# which runs: svelte-kit sync && svelte-check --tsconfig ./tsconfig.json
```

Run this before pushing — CI runs it as a separate job (`web-lint`).

## End-to-End Tests (Playwright)

**Location:** `myss-web/` — Playwright configuration and test files

**Run:**

```bash
make test-e2e
# equivalent to: cd myss-web && npm run test:e2e
# which runs: playwright test
```

E2E tests start a real browser (Chromium by default) and exercise the full stack — SvelteKit dev server talking to a running FastAPI instance. You need both services running locally before executing E2E tests (see [local-dev-setup.md](local-dev-setup.md)).

E2E tests are not run in CI as part of the standard pipeline (see below). They are intended for local verification of critical user journeys before major releases.

## CI Pipeline

CI is defined in `.github/workflows/ci.yml`. It runs on every push to any branch and on every pull request targeting `main`.

### Jobs that must pass before merge

| CI job | What it runs | Failure blocks merge |
|---|---|---|
| `api-lint` — API Lint & Type Check | `ruff check .` then `mypy app/` | Yes |
| `api-test` — API pytest | `python -m pytest -v --tb=short` | Yes |
| `web-lint` — Web Lint & Type Check | `npm run check` (svelte-check) | Yes |
| `web-test` — Web Vitest | `npm test` (vitest run) | Yes |

All four jobs run in parallel. All four must be green for a PR to be mergeable.

CI does **not** currently run Playwright E2E tests or coverage reporting. If you add new E2E coverage targets, coordinate with the team before adding them to the required check list.

### Python version in CI

CI uses Python 3.12 (`actions/setup-python@v5` with `python-version: "3.12"`). Use the same version locally to avoid subtle compatibility differences.

### Node version in CI

CI uses Node 20 (`actions/setup-node@v4` with `node-version: "20"`). npm dependencies are cached using `package-lock.json` as the cache key.

## Coverage

There is no automated coverage gate in CI yet. To generate a local coverage report:

```bash
cd myss-api && .venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

Install `pytest-cov` first if it is not already present:

```bash
pip install pytest-cov
```

For the frontend, Vitest supports coverage via `@vitest/coverage-v8`:

```bash
cd myss-web && npx vitest run --coverage
```

As the codebase grows, coverage targets will be formalised and added to CI.
