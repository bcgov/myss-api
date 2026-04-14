"""Tests for SR submit endpoint (Task 20)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.service_requests.models import SRSubmitResponse, SRDraftResponse, SRType
from app.domains.service_requests.service import ServiceRequestService
from app.routers.service_requests import _get_sr_service


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_STUB_SUBMIT_RESPONSE = SRSubmitResponse(
    sr_id="SR-001",
    sr_number="SR-NUM-001",
    submitted_at=_NOW,
)


def _make_stub_service(
    submit_response: SRSubmitResponse = _STUB_SUBMIT_RESPONSE,
) -> ServiceRequestService:
    svc = MagicMock(spec=ServiceRequestService)
    svc.submit_sr = AsyncMock(return_value=submit_response)
    svc.create_sr = AsyncMock(return_value=None)
    svc.get_form_schema = AsyncMock(return_value=None)
    svc.save_form_draft = AsyncMock(return_value=None)
    svc.get_draft = AsyncMock(return_value=None)
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
# POST /service-requests/{sr_id}/submit — submit SR
# ---------------------------------------------------------------------------


async def test_submit_sr_returns_200_with_sr_number(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "declaration_accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sr_id"] == "SR-001"
    assert data["sr_number"] == "SR-NUM-001"
    assert "submitted_at" in data


async def test_submit_sr_returns_422_when_declaration_false(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "declaration_accepted": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_submit_sr_returns_401_without_auth(ac):
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "declaration_accepted": True},
    )
    assert response.status_code == 401


async def test_submit_sr_returns_403_on_invalid_pin(ac, override_sr_service):
    from app.services.icm.exceptions import PINValidationError
    override_sr_service.submit_sr = AsyncMock(side_effect=PINValidationError("Invalid PIN"))
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "wrong", "declaration_accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Invalid PIN" in response.json()["detail"]


async def test_submit_sr_calls_service_with_correct_args(ac, override_sr_service):
    token = make_token("CLIENT")
    await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "spouse_pin": "5678", "declaration_accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    override_sr_service.submit_sr.assert_awaited_once_with(
        sr_id="SR-001",
        pin="1234",
        spouse_pin="5678",
        bceid_guid="user1",  # bceid_guid is None so falls back to user_id
        user_id="user1",
    )


async def test_submit_sr_response_has_required_fields(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "declaration_accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "sr_id" in data
    assert "sr_number" in data
    assert "submitted_at" in data


# ---------------------------------------------------------------------------
# POST submit → draft deleted → GET draft returns 404
# ---------------------------------------------------------------------------


async def test_submit_then_get_draft_returns_404(ac, override_sr_service):
    """After a successful submit, GET /draft returns 404 (draft was deleted)."""
    token = make_token("CLIENT")

    # Submit succeeds
    response = await ac.post(
        "/service-requests/SR-001/submit",
        json={"pin": "1234", "declaration_accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # get_draft returns None (draft deleted)
    override_sr_service.get_draft = AsyncMock(return_value=None)

    response = await ac.get(
        "/service-requests/SR-001/draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PDFGenerationService is called for PDF-requiring SR types
# ---------------------------------------------------------------------------


_NOW2 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_CRISIS_DRAFT = SRDraftResponse(
    sr_id="SR-CRISIS-001",
    sr_type=SRType.CRISIS_FOOD,
    draft_json={"answers": {"reason": "Emergency"}, "page_index": 0},
    updated_at=_NOW2,
)


async def test_pdf_generated_for_pdf_requiring_sr_type():
    """PDFGenerationService.generate is called for CRISIS_FOOD (a PDF-requiring type)."""
    from app.services.icm.service_requests import SiebelSRClient
    from app.domains.account.pin_service import PINService

    # Set up stubs
    mock_client = AsyncMock(spec=SiebelSRClient)
    mock_client.finalize_sr_form = AsyncMock(return_value={"sr_number": "SR-NUM-002"})

    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    svc = ServiceRequestService(sr_client=mock_client, draft_repo=None, pin_service=pin_svc)

    # Patch get_draft to return a CRISIS_FOOD draft, and PDF service stub
    with (
        patch.object(svc, "get_draft", return_value=_CRISIS_DRAFT),
        patch(
            "app.domains.service_requests.pdf_generation_service.PDFGenerationService"
        ) as MockPdfSvc,
    ):
        mock_pdf_instance = MockPdfSvc.return_value
        mock_pdf_instance.generate = AsyncMock(return_value=b"%PDF-mock")

        result = await svc.submit_sr(
            sr_id="SR-CRISIS-001",
            pin="1234",
            spouse_pin=None,
            bceid_guid="guid-123",
        )

        # PDF generation was called with the correct sr_type
        mock_pdf_instance.generate.assert_awaited_once_with(
            SRType.CRISIS_FOOD, {"reason": "Emergency"}
        )
        assert result.sr_number == "SR-NUM-002"


_ASSIST_DRAFT = SRDraftResponse(
    sr_id="SR-ASSIST-001",
    sr_type=SRType.ASSIST,
    draft_json={"answers": {"reason": "General"}, "page_index": 0},
    updated_at=_NOW2,
)


async def test_pdf_not_generated_for_non_pdf_sr_type():
    """PDFGenerationService.generate is NOT called for ASSIST (not a PDF-requiring type)."""
    from app.services.icm.service_requests import SiebelSRClient
    from app.domains.account.pin_service import PINService

    mock_client = AsyncMock(spec=SiebelSRClient)
    mock_client.finalize_sr_form = AsyncMock(return_value={"sr_number": "SR-NUM-003"})

    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    svc = ServiceRequestService(sr_client=mock_client, draft_repo=None, pin_service=pin_svc)

    with (
        patch.object(svc, "get_draft", return_value=_ASSIST_DRAFT),
        patch(
            "app.domains.service_requests.pdf_generation_service.PDFGenerationService"
        ) as MockPdfSvc,
    ):
        mock_pdf_instance = MockPdfSvc.return_value
        mock_pdf_instance.generate = AsyncMock(return_value=b"")

        await svc.submit_sr(
            sr_id="SR-ASSIST-001",
            pin="1234",
            spouse_pin=None,
            bceid_guid="guid-123",
        )

        # PDF generation should NOT be called
        mock_pdf_instance.generate.assert_not_awaited()
