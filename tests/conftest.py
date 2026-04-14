import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.cache import redis_client


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_redis_pool_between_tests():
    """pytest-asyncio creates a fresh event loop per test, but `_redis_pool` is a
    module-level singleton bound to the loop on first use. Clear it between tests
    so each test lazy-creates a pool on its own loop."""
    yield
    redis_client._redis_pool = None
