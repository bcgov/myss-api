"""Tests for Account API endpoints (Task 35)."""
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.account.models import (
    AccountInfoResponse,
    CaseMember,
    CaseMemberListResponse,
)
from app.domains.account.service import AccountService
from app.routers.account import _get_account_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_STUB_ACCOUNT_INFO = AccountInfoResponse(
    user_id="user1",
    email="user@example.com",
    phone_numbers=[{"phone_id": 1, "phone_number": "604-555-0100", "phone_type": "Home"}],
    case_number="CASE-001",
    case_status="Active",
)

_STUB_CASE_MEMBERS = CaseMemberListResponse(
    members=[
        CaseMember(name="Jane Doe", relationship="Spouse"),
        CaseMember(name="Child Doe", relationship="Dependent"),
    ]
)


def _make_stub_service() -> AccountService:
    svc = MagicMock(spec=AccountService)
    svc.get_profile = AsyncMock(return_value=_STUB_ACCOUNT_INFO)
    svc.update_contact = AsyncMock(return_value=None)
    svc.get_case_members = AsyncMock(return_value=_STUB_CASE_MEMBERS)
    svc.post_login_sync = AsyncMock(return_value=None)
    return svc


@pytest.fixture(autouse=True)
def override_account_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_account_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_account_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /account/profile
# ---------------------------------------------------------------------------


async def test_get_profile_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/account/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user1"
    assert data["email"] == "user@example.com"
    assert data["case_number"] == "CASE-001"


async def test_get_profile_returns_401_without_auth(ac):
    response = await ac.get("/account/profile")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /account/contact
# ---------------------------------------------------------------------------


async def test_update_contact_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.patch(
        "/account/contact",
        json={
            "email": "new@example.com",
            "email_confirm": "new@example.com",
            "phones": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_update_contact_email_mismatch_returns_422(ac):
    token = make_token("CLIENT")
    response = await ac.patch(
        "/account/contact",
        json={
            "email": "one@example.com",
            "email_confirm": "two@example.com",
            "phones": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_update_contact_delete_without_phone_id_returns_422(ac):
    token = make_token("CLIENT")
    response = await ac.patch(
        "/account/contact",
        json={
            "phones": [
                {
                    "phone_number": "604-555-0100",
                    "phone_type": "Home",
                    "operation": "DELETE",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_update_contact_returns_401_without_auth(ac):
    response = await ac.patch(
        "/account/contact",
        json={"email": "test@example.com", "email_confirm": "test@example.com"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /account/case-members
# ---------------------------------------------------------------------------


async def test_get_case_members_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/account/case-members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "members" in data
    assert len(data["members"]) == 2
    assert data["members"][0]["name"] == "Jane Doe"


async def test_get_case_members_returns_401_without_auth(ac):
    response = await ac.get("/account/case-members")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /account/post-login-sync
# ---------------------------------------------------------------------------


async def test_post_login_sync_returns_202(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/account/post-login-sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202


async def test_post_login_sync_returns_401_without_auth(ac):
    response = await ac.post("/account/post-login-sync")
    assert response.status_code == 401
