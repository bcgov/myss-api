"""Tests for Attachments API endpoints (Tasks 39 & 40)."""
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.attachments.models import ScanStatus
from app.domains.attachments.service import AttachmentService
from app.routers.attachments import _get_attachment_service
from app.services.icm.exceptions import ICMServiceUnavailableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _make_stub_service() -> AttachmentService:
    svc = MagicMock(spec=AttachmentService)
    from app.domains.attachments.models import UploadResponse, ScanStatusResponse, AttachmentSubmitResponse
    now = datetime.now(timezone.utc)
    svc.upload = AsyncMock(return_value=UploadResponse(
        scan_id="job-123",
        filename="test.pdf",
        uploaded_at=now,
    ))
    svc.get_scan_status = AsyncMock(return_value=ScanStatusResponse(
        scan_id="job-123",
        status=ScanStatus.CLEAN,
        scanned_at=now,
    ))
    svc.process_scan_result = AsyncMock(return_value=None)
    svc.submit_attachment = AsyncMock(return_value=AttachmentSubmitResponse(
        attachment_id="att-456",
        sr_id="SR-001",
        filename="test.pdf",
    ))
    svc.download_message_attachment = AsyncMock(return_value=(b"file content", "test.pdf"))
    svc.download_sr_attachment = AsyncMock(return_value=(b"sr content", "sr_doc.pdf"))
    return svc


@pytest.fixture(autouse=True)
def override_attachment_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_attachment_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_attachment_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# POST /attachments/upload
# ---------------------------------------------------------------------------


async def test_upload_returns_200_with_scan_id(ac):
    token = make_token("CLIENT")
    file_content = b"hello world"
    response = await ac.post(
        "/attachments/upload",
        files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data
    assert data["scan_id"] == "job-123"
    assert data["filename"] == "test.pdf"
    assert "uploaded_at" in data


async def test_upload_rejects_file_over_5mb(ac, override_attachment_service):
    token = make_token("CLIENT")
    large_content = b"x" * (5_242_880 + 1)
    response = await ac.post(
        "/attachments/upload",
        files={"file": ("big.pdf", io.BytesIO(large_content), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 413


async def test_upload_rejects_disallowed_mime_type(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/attachments/upload",
        files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash"), "application/x-sh")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 415


async def test_upload_returns_401_without_auth(ac):
    response = await ac.post(
        "/attachments/upload",
        files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /attachments/upload/{scan_id}/status
# ---------------------------------------------------------------------------


async def test_get_scan_status_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/upload/job-123/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scan_id"] == "job-123"
    assert data["status"] == ScanStatus.CLEAN
    assert "scanned_at" in data


async def test_get_scan_status_returns_404_when_not_found(ac, override_attachment_service):
    override_attachment_service.get_scan_status = AsyncMock(
        side_effect=ValueError("Scan job not found")
    )
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/upload/nonexistent/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_get_scan_status_returns_401_without_auth(ac):
    response = await ac.get("/attachments/upload/job-123/status")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /internal/av-scan-result  (webhook secret auth)
# ---------------------------------------------------------------------------


async def test_av_scan_result_updates_status(ac, override_attachment_service, monkeypatch):
    monkeypatch.setenv("AV_WEBHOOK_SECRET", "test-secret")
    now = datetime.now(timezone.utc).isoformat()
    response = await ac.post(
        "/internal/av-scan-result",
        json={"scan_id": "job-123", "status": "CLEAN", "scanned_at": now},
        headers={"X-Webhook-Secret": "test-secret"},
    )
    assert response.status_code == 200
    override_attachment_service.process_scan_result.assert_awaited_once()


# ---------------------------------------------------------------------------
# POST /attachments/sr/{sr_id}/submit
# ---------------------------------------------------------------------------


async def test_submit_returns_201_when_clean(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/attachments/sr/SR-001/submit",
        json={"scan_id": "job-123", "filename": "test.pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["attachment_id"] == "att-456"
    assert data["sr_id"] == "SR-001"
    assert data["filename"] == "test.pdf"


async def test_submit_returns_422_when_pending(ac, override_attachment_service):
    override_attachment_service.submit_attachment = AsyncMock(
        side_effect=ValueError("Scan not complete")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/attachments/sr/SR-001/submit",
        json={"scan_id": "job-pending", "filename": "test.pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "Scan not complete" in response.json()["detail"]


async def test_submit_returns_422_when_infected(ac, override_attachment_service):
    override_attachment_service.submit_attachment = AsyncMock(
        side_effect=ValueError("File failed virus scan")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/attachments/sr/SR-001/submit",
        json={"scan_id": "job-infected", "filename": "test.pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "File failed virus scan" in response.json()["detail"]


async def test_submit_returns_503_on_icm_error(ac, override_attachment_service):
    override_attachment_service.submit_attachment = AsyncMock(
        side_effect=ICMServiceUnavailableError("down")
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/attachments/sr/SR-001/submit",
        json={"scan_id": "job-123", "filename": "test.pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


async def test_submit_returns_401_without_auth(ac):
    response = await ac.post(
        "/attachments/sr/SR-001/submit",
        json={"scan_id": "job-123", "filename": "test.pdf"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /attachments/messages/{msg_id}/{attachment_id}/download
# ---------------------------------------------------------------------------


async def test_download_message_attachment_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/messages/MSG-001/att-001/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.content == b"file content"
    assert "attachment" in response.headers.get("content-disposition", "")


async def test_download_message_attachment_returns_503_on_icm_error(ac, override_attachment_service):
    override_attachment_service.download_message_attachment = AsyncMock(
        side_effect=ICMServiceUnavailableError("down")
    )
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/messages/MSG-001/att-001/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


async def test_download_message_attachment_returns_401_without_auth(ac):
    response = await ac.get("/attachments/messages/MSG-001/att-001/download")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /attachments/sr/{sr_id}/download
# ---------------------------------------------------------------------------


async def test_download_sr_attachment_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/sr/SR-001/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.content == b"sr content"
    assert "attachment" in response.headers.get("content-disposition", "")


async def test_download_sr_attachment_returns_503_on_icm_error(ac, override_attachment_service):
    override_attachment_service.download_sr_attachment = AsyncMock(
        side_effect=ICMServiceUnavailableError("down")
    )
    token = make_token("CLIENT")
    response = await ac.get(
        "/attachments/sr/SR-001/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


async def test_download_sr_attachment_returns_401_without_auth(ac):
    response = await ac.get("/attachments/sr/SR-001/download")
    assert response.status_code == 401
