"""Tests for SR create/draft endpoints (Task 19)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.service_requests.models import (
    DynamicFormField,
    DynamicFormPage,
    DynamicFormSchema,
    DynamicFormType,
    SRDraftResponse,
    SRType,
)
from app.domains.service_requests.service import ServiceRequestService
from app.services.icm.exceptions import ICMActiveSRConflictError
from app.routers.service_requests import _get_sr_service


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_STUB_DRAFT = SRDraftResponse(
    sr_id="SR-NEW-001",
    sr_type=SRType.ASSIST,
    draft_json=None,
    updated_at=_NOW,
)

_STUB_SCHEMA = DynamicFormSchema(
    form_type=DynamicFormType.SR,
    sr_type=SRType.ASSIST,
    pages=[
        DynamicFormPage(
            page_index=0,
            title="Application Details",
            fields=[
                DynamicFormField(
                    field_id="reason",
                    label="Reason for Request",
                    field_type="textarea",
                    required=True,
                )
            ],
        )
    ],
    total_pages=1,
)

_STUB_SAVED_DRAFT = SRDraftResponse(
    sr_id="SR-NEW-001",
    sr_type=SRType.ASSIST,
    draft_json={"answers": {"reason": "Need help"}, "page_index": 0},
    updated_at=_NOW,
)


def _make_stub_service(
    create_draft: SRDraftResponse = _STUB_DRAFT,
    form_schema: DynamicFormSchema | None = _STUB_SCHEMA,
    saved_draft: SRDraftResponse | None = _STUB_SAVED_DRAFT,
    get_draft_val: SRDraftResponse | None = _STUB_SAVED_DRAFT,
) -> ServiceRequestService:
    svc = MagicMock(spec=ServiceRequestService)
    svc.create_sr = AsyncMock(return_value=create_draft)
    svc.get_form_schema = AsyncMock(return_value=form_schema)
    svc.save_form_draft = AsyncMock(return_value=saved_draft)
    svc.get_draft = AsyncMock(return_value=get_draft_val)
    svc.list_srs = AsyncMock(return_value=None)
    svc.get_eligible_types = AsyncMock(return_value=[])
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
# POST /service-requests — create SR
# ---------------------------------------------------------------------------


async def test_create_sr_returns_201(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests",
        json={"sr_type": "ASSIST"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sr_id"] == "SR-NEW-001"
    assert data["sr_type"] == "ASSIST"
    assert data["draft_json"] is None


async def test_create_sr_calls_service(ac, override_sr_service):
    token = make_token("CLIENT")
    await ac.post(
        "/service-requests",
        json={"sr_type": "ASSIST"},
        headers={"Authorization": f"Bearer {token}"},
    )
    override_sr_service.create_sr.assert_awaited_once_with(
        sr_type=SRType.ASSIST,
        profile_id="user1",
        user_id="user1",
    )


async def test_create_sr_returns_401_without_auth(ac):
    response = await ac.post(
        "/service-requests",
        json={"sr_type": "ASSIST"},
    )
    assert response.status_code == 401


async def test_create_sr_returns_422_with_invalid_sr_type(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests",
        json={"sr_type": "INVALID_TYPE_XYZ"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_create_sr_returns_409_on_active_conflict(ac, override_sr_service):
    """When ICM reports an active SR conflict, the endpoint returns 409."""
    override_sr_service.create_sr = AsyncMock(
        side_effect=ICMActiveSRConflictError("Active SR exists", error_code="ICM_ERR_ACTIVE_SR_CONFLICT")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests",
        json={"sr_type": "ASSIST"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /service-requests/{sr_id}/draft — retrieve draft
# ---------------------------------------------------------------------------


async def test_get_draft_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-NEW-001/draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sr_id"] == "SR-NEW-001"
    assert data["draft_json"]["answers"]["reason"] == "Need help"


async def test_get_draft_returns_404_when_missing(ac, override_sr_service):
    override_sr_service.get_draft = AsyncMock(return_value=None)
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-UNKNOWN/draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /service-requests/{sr_id}/form — get form schema
# ---------------------------------------------------------------------------


async def test_get_form_schema_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-NEW-001/form",
        params={"sr_type": "ASSIST"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["form_type"] == "SR"
    assert data["sr_type"] == "ASSIST"
    assert data["total_pages"] == 1
    assert len(data["pages"]) == 1
    page = data["pages"][0]
    assert page["page_index"] == 0
    assert page["title"] == "Application Details"
    assert len(page["fields"]) == 1
    field = page["fields"][0]
    assert field["field_id"] == "reason"
    assert field["field_type"] == "textarea"
    assert field["required"] is True


async def test_get_form_schema_returns_401_without_auth(ac):
    response = await ac.get("/service-requests/SR-NEW-001/form", params={"sr_type": "ASSIST"})
    assert response.status_code == 401


async def test_get_form_schema_returns_404_for_non_dynamic_type(ac, override_sr_service):
    """Non-dynamic SR types return 404 via SRTypeRegistry.is_dynamic() check."""
    override_sr_service.get_form_schema = AsyncMock(return_value=None)
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-UNKNOWN/form",
        params={"sr_type": "DIRECT_DEPOSIT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_get_form_schema_returns_422_without_sr_type_param(ac):
    """sr_type query param is required."""
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-NEW-001/form",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /service-requests/{sr_id}/form — save draft
# ---------------------------------------------------------------------------


async def test_update_form_draft_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.put(
        "/service-requests/SR-NEW-001/form",
        json={"answers": {"reason": "Need help"}, "page_index": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sr_id"] == "SR-NEW-001"
    assert data["draft_json"]["answers"]["reason"] == "Need help"


async def test_update_form_draft_returns_401_without_auth(ac):
    response = await ac.put(
        "/service-requests/SR-NEW-001/form",
        json={"answers": {"reason": "Need help"}, "page_index": 0},
    )
    assert response.status_code == 401


async def test_update_form_draft_returns_404_when_draft_not_found(ac, override_sr_service):
    override_sr_service.save_form_draft = AsyncMock(return_value=None)
    token = make_token("CLIENT")
    response = await ac.put(
        "/service-requests/SR-DOES-NOT-EXIST/form",
        json={"answers": {"reason": "Need help"}, "page_index": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
