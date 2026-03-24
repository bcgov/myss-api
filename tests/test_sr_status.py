"""Tests for SR status (GET /{sr_id}) and withdraw (POST /{sr_id}/withdraw) endpoints (Task 21)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.service_requests.models import SRDetailResponse, SRType
from app.domains.service_requests.service import ServiceRequestService
from app.routers.service_requests import _get_sr_service
from app.services.icm.exceptions import ICMError, ICMSRAlreadyWithdrawnError


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_STUB_DETAIL = SRDetailResponse(
    sr_id="SR-001",
    sr_type=SRType.ASSIST,
    sr_number="SR-NUM-001",
    status="Pending",
    client_name="Test User",
    created_at=_NOW,
    answers={"reason": "need help"},
    attachments=[],
)


def _make_stub_service(
    detail: SRDetailResponse | None = _STUB_DETAIL,
) -> ServiceRequestService:
    svc = MagicMock(spec=ServiceRequestService)
    svc.get_sr_detail = AsyncMock(return_value=detail)
    svc.withdraw_sr = AsyncMock(return_value=None)
    svc.list_srs = AsyncMock(return_value=None)
    svc.get_eligible_types = AsyncMock(return_value=[])
    svc.create_sr = AsyncMock(return_value=None)
    svc.get_form_schema = AsyncMock(return_value=None)
    svc.save_form_draft = AsyncMock(return_value=None)
    svc.get_draft = AsyncMock(return_value=None)
    svc.submit_sr = AsyncMock(return_value=None)
    return svc


@pytest.fixture(autouse=True)
def override_sr_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_sr_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_sr_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /service-requests/{sr_id} — get SR detail
# ---------------------------------------------------------------------------


async def test_get_sr_detail_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sr_id"] == "SR-001"
    assert data["sr_number"] == "SR-NUM-001"
    assert data["status"] == "Pending"
    assert data["client_name"] == "Test User"
    assert "created_at" in data


async def test_get_sr_detail_returns_404_for_unknown_sr(ac, override_sr_service):
    override_sr_service.get_sr_detail = AsyncMock(return_value=None)
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/UNKNOWN-SR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_get_sr_detail_returns_401_without_auth(ac):
    response = await ac.get("/service-requests/SR-001")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /service-requests/{sr_id}/withdraw — withdraw SR
# ---------------------------------------------------------------------------


async def test_withdraw_sr_returns_204(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/withdraw",
        json={"reason": "No longer needed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


async def test_withdraw_sr_returns_401_without_auth(ac):
    response = await ac.post(
        "/service-requests/SR-001/withdraw",
        json={"reason": "No longer needed"},
    )
    assert response.status_code == 401


async def test_withdraw_sr_returns_409_when_already_withdrawn(ac, override_sr_service):
    override_sr_service.withdraw_sr = AsyncMock(
        side_effect=ICMSRAlreadyWithdrawnError("SR is already withdrawn", error_code="ICM_ERR_SR_ALREADY_WITHDRAWN")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/withdraw",
        json={"reason": "Duplicate request"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "already withdrawn" in response.json()["detail"].lower()
