"""Tests for SupportViewSession + impersonation endpoints (Task 44)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import jwt as pyjwt
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.cache.redis_client import get_redis
from app.dependencies.require_support_view_session import (
    clear_sessions,
    get_session,
    set_session,
)
from app.models.admin import SupportViewSessionData
from app.routers.admin.support_view import _get_admin_service


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def make_token(
    sub: str = "worker1",
    role: str = "WORKER",
    idir_username: str | None = "jdoe",
    bceid_guid: str | None = None,
    secret: str = "change-me-in-production",
) -> str:
    payload: dict = {"sub": sub, "role": role}
    if idir_username is not None:
        payload["idir_username"] = idir_username
    if bceid_guid is not None:
        payload["bceid_guid"] = bceid_guid
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis():
    """Shared FakeRedis instance for each test."""
    return FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
async def _clear_sessions(fake_redis):
    """Clear Redis session store between tests."""
    await clear_sessions(fake_redis)
    yield
    await clear_sessions(fake_redis)


@pytest.fixture
def mock_admin_client():
    client = MagicMock()
    client.search_profiles = AsyncMock(
        return_value={
            "results": [
                {
                    "portal_id": "portal-123",
                    "bceid_guid": "bceid-abc",
                    "full_name": "Jane Doe",
                    "case_number": "C-001",
                    "case_status": "Active",
                }
            ],
            "total": 1,
            "page": 1,
        }
    )
    client.get_client_profile = AsyncMock(
        return_value={
            "portal_id": "portal-123",
            "bceid_guid": "bceid-abc",
            "full_name": "Jane Doe",
            "case_number": "C-001",
            "case_status": "Active",
            "contact_id": "contact-xyz",
            "link_code": "LINK123",
        }
    )
    return client


@pytest.fixture
async def ac(mock_admin_client, fake_redis) -> AsyncClient:
    async def _mock_get_redis():
        yield fake_redis

    app.dependency_overrides[_get_admin_service] = lambda: mock_admin_client
    app.dependency_overrides[get_redis] = _mock_get_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(_get_admin_service, None)
    app.dependency_overrides.pop(get_redis, None)


# ---------------------------------------------------------------------------
# 1. test_search_returns_200
# ---------------------------------------------------------------------------


async def test_search_returns_200(ac, mock_admin_client):
    """Worker token with POST body returns 200 with results."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/search",
        json={"first_name": "Jane", "last_name": "Doe", "page": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["total"] == 1
    mock_admin_client.search_profiles.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. test_search_returns_401_without_auth
# ---------------------------------------------------------------------------


async def test_search_returns_401_without_auth(ac):
    """No token returns 401."""
    response = await ac.post(
        "/admin/support-view/search",
        json={"first_name": "Jane"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 3. test_search_returns_403_for_client
# ---------------------------------------------------------------------------


async def test_search_returns_403_for_client(ac):
    """CLIENT role gets 403."""
    token = make_token(role="CLIENT", idir_username=None)
    response = await ac.post(
        "/admin/support-view/search",
        json={"first_name": "Jane"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. test_tombstone_creates_session
# ---------------------------------------------------------------------------


async def test_tombstone_creates_session(ac, mock_admin_client, fake_redis):
    """POST tombstone with valid client_bceid_guid returns 200 with session data."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/tombstone",
        json={"client_bceid_guid": "bceid-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_bceid_guid"] == "bceid-abc"
    assert "expires_at" in data
    assert "session_token" in data
    # Session should be stored
    assert await get_session("jdoe:bceid-abc", fake_redis) is not None


# ---------------------------------------------------------------------------
# 5. test_tombstone_rejects_self_impersonation
# ---------------------------------------------------------------------------


async def test_tombstone_rejects_self_impersonation(ac):
    """POST tombstone where client_bceid_guid == user.bceid_guid returns 400."""
    # Worker with dual identity: IDIR auth + BCeID guid
    token = make_token(
        sub="worker1",
        role="WORKER",
        idir_username="jdoe",
        bceid_guid="dual-identity-guid",
    )
    response = await ac.post(
        "/admin/support-view/tombstone",
        json={"client_bceid_guid": "dual-identity-guid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "self-impersonation" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. test_delete_tombstone_ends_session
# ---------------------------------------------------------------------------


async def test_delete_tombstone_ends_session(ac, mock_admin_client, fake_redis):
    """DELETE tombstone returns 204 and session is gone."""
    # First create a session
    token = make_token(role="WORKER", idir_username="jdoe")
    create_resp = await ac.post(
        "/admin/support-view/tombstone",
        json={"client_bceid_guid": "bceid-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    assert await get_session("jdoe:bceid-abc", fake_redis) is not None

    # Delete the session
    delete_resp = await ac.delete(
        "/admin/support-view/tombstone",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Support-View-Client": "bceid-abc",
        },
    )
    assert delete_resp.status_code == 204
    assert await get_session("jdoe:bceid-abc", fake_redis) is None


# ---------------------------------------------------------------------------
# 7. test_client_data_requires_session
# ---------------------------------------------------------------------------


async def test_client_data_requires_session(ac):
    """GET client-data without session returns 401."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.get(
        "/admin/support-view/client-data/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Support-View-Client": "bceid-abc",
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 8. test_client_data_with_valid_session
# ---------------------------------------------------------------------------


async def test_client_data_with_valid_session(ac, mock_admin_client):
    """Create session then GET client-data returns 200."""
    token = make_token(role="WORKER", idir_username="jdoe")

    # Create session
    create_resp = await ac.post(
        "/admin/support-view/tombstone",
        json={"client_bceid_guid": "bceid-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200

    # Access client data
    response = await ac.get(
        "/admin/support-view/client-data/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Support-View-Client": "bceid-abc",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resource"] == "profile"
    assert data["client_bceid_guid"] == "bceid-abc"


# ---------------------------------------------------------------------------
# 9. test_expired_session_returns_401
# ---------------------------------------------------------------------------


async def test_expired_session_returns_401(ac, fake_redis):
    """Expired session in store returns 401."""
    past_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    expired_session = SupportViewSessionData(
        worker_idir="jdoe",
        client_portal_id="portal-123",
        client_bceid_guid="bceid-abc",
        activated_at=past_time - timedelta(minutes=15),
        expires_at=past_time,
    )
    await set_session("jdoe:bceid-abc", expired_session, fake_redis)

    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.get(
        "/admin/support-view/client-data/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Support-View-Client": "bceid-abc",
        },
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
    # Expired session should be removed
    assert await get_session("jdoe:bceid-abc", fake_redis) is None


# ---------------------------------------------------------------------------
# 10. test_search_paginated
# ---------------------------------------------------------------------------


async def test_search_rejects_invalid_sin(ac):
    """Invalid (non-Luhn) SIN returns 422."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/search",
        json={"sin": "000000001"},  # invalid Luhn checksum
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_search_rejects_invalid_name(ac):
    """Invalid name (digits) returns 422."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/search",
        json={"first_name": "Jane123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_search_accepts_valid_sin(ac, mock_admin_client):
    """A valid Luhn SIN is accepted (046454286 is a standard test SIN)."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/search",
        json={"sin": "046454286"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_search_paginated(ac, mock_admin_client):
    """Verify page param is forwarded to the admin client."""
    token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/support-view/search",
        json={"page": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    # Verify the mock was called with page=3
    call_kwargs = mock_admin_client.search_profiles.call_args
    assert call_kwargs.kwargs["page"] == 3
