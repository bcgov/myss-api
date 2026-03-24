"""Tests for AuditMiddleware: skip audit on 401/403 (Task 5 — security hardening)."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import jwt as pyjwt
from httpx import AsyncClient, ASGITransport

import app.auth.dependencies as auth_mod
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("ICM_BASE_URL", "https://test.example.com")
    monkeypatch.setenv("ICM_CLIENT_ID", "test")
    monkeypatch.setenv("ICM_CLIENT_SECRET", "test")
    monkeypatch.setenv("ICM_TOKEN_URL", "https://test.example.com/token")


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests: audit must NOT fire on auth failures
# ---------------------------------------------------------------------------


async def test_audit_skipped_on_401(ac):
    """A request to /admin/ that returns 401 must NOT call _persist_audit_record."""
    with patch(
        "app.middleware.audit_middleware._persist_audit_record", new_callable=AsyncMock
    ) as mock_persist:
        # No Authorization header → 401
        response = await ac.post(
            "/admin/support-view/search",
            json={"first_name": "Test"},
        )

    assert response.status_code == 401
    mock_persist.assert_not_called()


async def test_audit_skipped_on_403(ac):
    """A request to /admin/ that returns 403 must NOT call _persist_audit_record."""
    # Create a valid JWT with CLIENT role (not WORKER) → should yield 403
    token = pyjwt.encode(
        {"sub": "u1", "role": "CLIENT"}, auth_mod._get_jwt_secret(), algorithm="HS256"
    )

    with patch(
        "app.middleware.audit_middleware._persist_audit_record", new_callable=AsyncMock
    ) as mock_persist:
        response = await ac.post(
            "/admin/support-view/search",
            json={"first_name": "Test"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    mock_persist.assert_not_called()
