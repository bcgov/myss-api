"""Tests for SR list endpoint (Task 18)."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import jwt as pyjwt
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.domains.service_requests.models import (
    SRListResponse,
    SRSummary,
    SRType,
    SRTypeMetadata,
)
from app.domains.service_requests.service import ServiceRequestService
from app.services.icm.service_requests import SiebelSRClient
from app.routers.service_requests import _get_sr_service


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _stub_sr_client() -> SiebelSRClient:
    """Create a SiebelSRClient stub with mocked methods."""
    client = AsyncMock(spec=SiebelSRClient)
    client.get_sr_list = AsyncMock(return_value={
        "items": [
            {
                "sr_id": "SR-001",
                "sr_type": "ASSIST",
                "sr_number": "2024-001",
                "status": "Open",
                "client_name": "Jane Doe",
                "created_at": "2024-01-15T10:00:00+00:00",
            }
        ],
        "total": 1,
    })
    client.get_eligible_types = AsyncMock(return_value={
        "types": [
            {
                "sr_type": "ASSIST",
                "display_name": "Application for Assistance",
                "requires_pin": True,
                "has_attachments": True,
                "max_active": 1,
            },
            {
                "sr_type": "BUS_PASS",
                "display_name": "Bus Pass",
                "requires_pin": False,
                "has_attachments": False,
                "max_active": 1,
            },
        ]
    })
    return client


@pytest.fixture(autouse=True)
def override_sr_service():
    """Override the SR service dependency with a real service wrapping a stubbed SiebelSRClient."""
    stub_client = _stub_sr_client()
    svc = ServiceRequestService(sr_client=stub_client)
    app.dependency_overrides[_get_sr_service] = lambda: svc
    yield stub_client
    app.dependency_overrides.pop(_get_sr_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Test: GET /service-requests — list
# ---------------------------------------------------------------------------

async def test_list_srs_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["sr_id"] == "SR-001"
    assert item["sr_type"] == "ASSIST"
    assert item["status"] == "Open"


async def test_list_srs_calls_siebel_client(ac, override_sr_service):
    """Verify the SiebelSRClient stub is actually called with the correct profile_id."""
    token = make_token("CLIENT")
    await ac.get(
        "/service-requests",
        headers={"Authorization": f"Bearer {token}"},
    )
    override_sr_service.get_sr_list.assert_awaited_once_with("user1")


async def test_list_srs_returns_401_without_auth(ac):
    response = await ac.get("/service-requests")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: GET /service-requests/eligible-types
# ---------------------------------------------------------------------------

async def test_eligible_types_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/eligible-types",
        params={"case_status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    types_returned = {item["sr_type"] for item in data}
    assert types_returned == {"ASSIST", "BUS_PASS"}


async def test_eligible_types_calls_siebel_client(ac, override_sr_service):
    """Verify the SiebelSRClient stub is called with correct profile_id and case_status."""
    token = make_token("CLIENT")
    await ac.get(
        "/service-requests/eligible-types",
        params={"case_status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    override_sr_service.get_eligible_types.assert_awaited_once_with("user1", "ACTIVE")


async def test_eligible_types_returns_401_without_auth(ac):
    response = await ac.get(
        "/service-requests/eligible-types",
        params={"case_status": "ACTIVE"},
    )
    assert response.status_code == 401


async def test_eligible_types_returns_422_without_case_status(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/eligible-types",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test: SRType enum completeness — all 19 values
# ---------------------------------------------------------------------------

def test_srtype_enum_has_all_19_values():
    expected = {
        "ASSIST",
        "RREINSTATE",
        "CRISIS_FOOD",
        "CRISIS_SHELTER",
        "CRISIS_CLOTHING",
        "CRISIS_UTILITIES",
        "CRISIS_MED_TRANSPORT",
        "DIRECT_DEPOSIT",
        "DIET",
        "NATAL",
        "MED_TRANSPORT_LOCAL",
        "MED_TRANSPORT_NON_LOCAL",
        "RECONSIDERATION",
        "RECON_SUPPLEMENT",
        "RECON_EXTENSION",
        "STREAMLINED",
        "BUS_PASS",
        "PWD_DESIGNATION",
        "PPMB",
    }
    actual = {member.value for member in SRType}
    assert actual == expected
    assert len(actual) == 19
