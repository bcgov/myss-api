from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.domains.account.pin_service import PINService
from app.middleware.rate_limiter import limiter
from app.routers.pin import _get_pin_service


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Reset limiter counters between tests."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def _override_pin_service():
    svc = MagicMock(spec=PINService)
    svc.validate = AsyncMock(return_value=True)
    app.dependency_overrides[_get_pin_service] = lambda: svc
    yield svc
    app.dependency_overrides.pop(_get_pin_service, None)


def _make_token() -> str:
    return pyjwt.encode(
        {"sub": "user1", "role": "CLIENT"},
        "change-me-in-production",
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_pin_validate_is_rate_limited():
    token = _make_token()
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 5 requests allowed per minute; 6th should return 429
        seen_429 = False
        for _ in range(7):
            response = await ac.post(
                "/auth/pin/validate", json={"pin": "0000"}, headers=headers
            )
            if response.status_code == 429:
                seen_429 = True
                break
        assert seen_429, "Expected 429 after exceeding rate limit"
