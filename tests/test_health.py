import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_session
from app.cache.redis_client import get_redis
import fakeredis.aioredis


@pytest.fixture
async def client():
    # Override FastAPI dependencies for unit tests
    async def mock_get_session():
        yield None  # health check catches exceptions; None triggers the error path → "degraded"

    fake_redis = fakeredis.aioredis.FakeRedis()

    async def mock_get_redis():
        yield fake_redis

    app.dependency_overrides[get_session] = mock_get_session
    app.dependency_overrides[get_redis] = mock_get_redis

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "db" in data
    assert "redis" in data
    # With mock_get_session yielding None, db will be "error" (exception on None.execute)
    # With fakeredis, redis will be "ok"
    assert data["redis"] == "ok"
    assert data["status"] in ("ok", "degraded")
