"""Tests for Employment Plans API endpoints (Tasks 32 and 33)."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.employment_plans.models import (
    EPStatus,
    EmploymentPlan,
    EPListResponse,
    EPDetailResponse,
    EPSignResponse,
)
from app.domains.employment_plans.service import EmploymentPlanService
from app.routers.employment_plans import _get_ep_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

_STUB_PLAN_1 = EmploymentPlan(
    ep_id=1,
    message_id=100,
    icm_attachment_id="ATT-001",
    status=EPStatus.PENDING_SIGNATURE,
    plan_date=date(2026, 3, 1),
    message_deleted=False,
)

_STUB_PLAN_2 = EmploymentPlan(
    ep_id=2,
    message_id=200,
    icm_attachment_id="ATT-002",
    status=EPStatus.SUBMITTED,
    plan_date=date(2026, 1, 15),
    message_deleted=False,
)

_STUB_EP_LIST = EPListResponse(plans=[_STUB_PLAN_1, _STUB_PLAN_2])

_STUB_EP_DETAIL = EPDetailResponse(
    ep_id=1,
    message_id=100,
    icm_attachment_id="ATT-001",
    status=EPStatus.PENDING_SIGNATURE,
    plan_date=date(2026, 3, 1),
    message_deleted=False,
)

_STUB_SIGN_RESPONSE = EPSignResponse(
    ep_id=1,
    signed_at=_NOW,
)


def _make_stub_service() -> EmploymentPlanService:
    svc = MagicMock(spec=EmploymentPlanService)
    svc.list_plans = AsyncMock(return_value=_STUB_EP_LIST)
    svc.get_detail = AsyncMock(return_value=_STUB_EP_DETAIL)
    svc.sign_and_send = AsyncMock(return_value=_STUB_SIGN_RESPONSE)
    return svc


@pytest.fixture(autouse=True)
def override_ep_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_ep_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_ep_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /employment-plans
# ---------------------------------------------------------------------------


async def test_list_plans_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/employment-plans",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) == 2
    assert data["plans"][0]["ep_id"] == 1


async def test_service_sorts_plans_by_date_descending():
    """Unit test: EmploymentPlanService.list_plans sorts by plan_date descending."""
    mock_client = MagicMock()
    mock_client.get_ep_list = AsyncMock(return_value={
        "plans": [
            {
                "ep_id": 2,
                "message_id": 200,
                "icm_attachment_id": "ATT-002",
                "status": "Submitted",
                "plan_date": "2026-01-15",
                "message_deleted": False,
            },
            {
                "ep_id": 1,
                "message_id": 100,
                "icm_attachment_id": "ATT-001",
                "status": "PendingSignature",
                "plan_date": "2026-03-01",
                "message_deleted": False,
            },
        ]
    })

    svc = EmploymentPlanService(client=mock_client)
    result = await svc.list_plans("user1")

    # Should be sorted descending: 2026-03-01 (ep_id=1) before 2026-01-15 (ep_id=2)
    assert len(result.plans) == 2
    assert result.plans[0].ep_id == 1
    assert result.plans[1].ep_id == 2


async def test_list_plans_returns_401_without_auth(ac):
    response = await ac.get("/employment-plans")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /employment-plans/{ep_id}
# ---------------------------------------------------------------------------


async def test_get_detail_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/employment-plans/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ep_id"] == 1
    assert data["icm_attachment_id"] == "ATT-001"
    assert data["status"] == EPStatus.PENDING_SIGNATURE.value


async def test_get_detail_returns_401_without_auth(ac):
    response = await ac.get("/employment-plans/1")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /employment-plans/{ep_id}/sign
# ---------------------------------------------------------------------------


async def test_sign_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/employment-plans/1/sign",
        json={"pin": "1234", "message_id": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ep_id"] == 1
    assert "signed_at" in data


async def test_sign_returns_403_on_invalid_pin(ac, override_ep_service):
    override_ep_service.sign_and_send = AsyncMock(side_effect=ValueError("Invalid PIN"))

    token = make_token("CLIENT")
    response = await ac.post(
        "/employment-plans/1/sign",
        json={"pin": "wrong", "message_id": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Invalid PIN" in response.json()["detail"]


async def test_sign_returns_401_without_auth(ac):
    response = await ac.post(
        "/employment-plans/1/sign",
        json={"pin": "1234", "message_id": 100},
    )
    assert response.status_code == 401
