# Running Tests

This document covers all test layers, how to run them locally, and what CI requires before a PR can merge.

## Quick reference

All commands assume you're inside the project venv (see `local-dev-setup.md`).

| Goal | Command |
|------|---------|
| Run all tests | `python -m pytest -v` |
| Run a single file | `python -m pytest tests/test_account.py -v` |
| Run a single test | `python -m pytest tests/test_account.py::test_name -v` |
| Run only unit tests | `python -m pytest tests/domains/ -v` |
| Run only integration | `python -m pytest tests/integration/ -v` |
| Lint | `ruff check .` |
| Type-check | `mypy app/` |
| Coverage (if installed) | `python -m pytest --cov=app --cov-report=term-missing` |

Frontend tests live in the `myss-web` repo — see that project's
`running-tests.md` for details.

## Backend Tests (pytest)

**Location:** `myss-api/tests/`

**Run:**

```bash
python -m pytest
```

For more verbose output during development:

```bash
python -m pytest -v --tb=short
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
ruff check .
mypy app/
```

- **ruff:** line length 100, target Python 3.12 (configured in `pyproject.toml`)
- **mypy:** strict mode, `ignore_missing_imports = true`

Fix ruff errors automatically with `ruff check . --fix`. mypy errors must be resolved manually.

## Frontend tests

Frontend tests (`npm test`, Playwright E2E) are owned by the `myss-web`
repository. See the `running-tests.md` in that repo.

## CI checks

| Job | What it runs | Blocks merge |
|-----|--------------|--------------|
| `lint` | `ruff check .` + `mypy app/` | Yes |
| `test` | `python -m pytest -v` (full suite) | Yes |

CI is defined in `.github/workflows/ci.yml`. It runs on every push and every pull request targeting `main`. CI uses Python 3.12 (`actions/setup-python@v5` with `python-version: "3.12"`). Use the same version locally to avoid subtle compatibility differences.

## Coverage

There is no automated coverage gate in CI yet. To generate a local coverage report:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

Install `pytest-cov` first if it is not already present:

```bash
pip install pytest-cov
```

As the codebase grows, coverage targets will be formalised and added to CI.
