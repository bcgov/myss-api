"""Tests for PIN API endpoints (Task 36)."""
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.account.pin_service import PINService
from app.routers.pin import _get_pin_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _make_stub_service(validate_result: bool = True) -> PINService:
    svc = MagicMock(spec=PINService)
    svc.validate = AsyncMock(return_value=validate_result)
    svc.change_pin = AsyncMock(return_value=None)
    svc.request_reset = AsyncMock(return_value=None)
    svc.confirm_reset = AsyncMock(return_value=None)
    return svc


@pytest.fixture(autouse=True)
def override_pin_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_pin_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_pin_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# POST /auth/pin/validate
# ---------------------------------------------------------------------------


async def test_validate_pin_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/validate",
        json={"pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "valid"


async def test_validate_pin_invalid_returns_403(ac, override_pin_service):
    override_pin_service.validate = AsyncMock(return_value=False)
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/validate",
        json={"pin": "9999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_validate_pin_non_numeric_returns_422(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/validate",
        json={"pin": "abcd"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_validate_pin_returns_401_without_auth(ac):
    response = await ac.post("/auth/pin/validate", json={"pin": "1234"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/pin/change
# ---------------------------------------------------------------------------


async def test_change_pin_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/change",
        json={"current_pin": "1234", "new_pin": "5678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "changed"


async def test_change_pin_wrong_current_returns_403(ac, override_pin_service):
    override_pin_service.change_pin = AsyncMock(side_effect=ValueError("Current PIN is incorrect"))
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/change",
        json={"current_pin": "0000", "new_pin": "5678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Current PIN is incorrect" in response.json()["detail"]


async def test_change_pin_returns_401_without_auth(ac):
    response = await ac.post(
        "/auth/pin/change",
        json={"current_pin": "1234", "new_pin": "5678"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/pin/reset-request
# ---------------------------------------------------------------------------


async def test_reset_request_returns_202(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/reset-request",
        json={"email": "user@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


async def test_reset_request_returns_401_without_auth(ac):
    response = await ac.post(
        "/auth/pin/reset-request",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/pin/reset-confirm
# ---------------------------------------------------------------------------


async def test_reset_confirm_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/reset-confirm",
        json={"token": "valid-token-abc", "new_pin": "5678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "reset"


async def test_reset_confirm_invalid_token_returns_410(ac, override_pin_service):
    override_pin_service.confirm_reset = AsyncMock(
        side_effect=ValueError("Token is invalid or expired")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/auth/pin/reset-confirm",
        json={"token": "bad-token", "new_pin": "5678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 410
    assert "Token is invalid or expired" in response.json()["detail"]


async def test_reset_confirm_returns_401_without_auth(ac):
    response = await ac.post(
        "/auth/pin/reset-confirm",
        json={"token": "some-token", "new_pin": "5678"},
    )
    assert response.status_code == 401
