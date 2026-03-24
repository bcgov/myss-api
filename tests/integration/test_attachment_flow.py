"""Integration test for full attachment upload → AV scan → submit lifecycle.

Mocks at the SiebelAttachmentClient boundary so that the real AttachmentService
logic runs, while the external ICM HTTP calls are stubbed.

The module-level _scan_jobs dict in AttachmentService is cleared between tests.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import jwt as pyjwt
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.domains.attachments import service as attachment_service_module
from app.domains.attachments.service import AttachmentService
from app.routers.attachments import _get_attachment_service

_AV_WEBHOOK_SECRET = "integration-test-secret"


def make_token(role="CLIENT", secret="change-me-in-production"):
    return pyjwt.encode({"sub": "user1", "role": role}, secret, algorithm="HS256")


def _stub_icm_client():
    """Create a SiebelAttachmentClient stub with mocked methods."""
    client = AsyncMock()
    client.upload_attachment = AsyncMock(return_value={"attachment_id": "ATT-001"})
    client.get_message_attachment = AsyncMock(return_value={"content": b"data", "filename": "test.pdf"})
    client.get_sr_attachment = AsyncMock(return_value={"content": b"data", "filename": "test.pdf"})
    return client


@pytest.fixture(autouse=True)
def _set_av_webhook_secret(monkeypatch):
    """Set the AV webhook secret for integration tests."""
    monkeypatch.setenv("AV_WEBHOOK_SECRET", _AV_WEBHOOK_SECRET)


@pytest.fixture(autouse=True)
def clear_scan_jobs():
    """Clear the module-level _scan_jobs dict before and after each test."""
    attachment_service_module._scan_jobs.clear()
    yield
    attachment_service_module._scan_jobs.clear()


@pytest.fixture
def real_service_with_mock_client():
    """Create a real AttachmentService with a mocked ICM client and override dependency."""
    icm_client = _stub_icm_client()
    svc = AttachmentService(client=icm_client)
    app.dependency_overrides[_get_attachment_service] = lambda: svc
    yield svc, icm_client
    app.dependency_overrides.pop(_get_attachment_service, None)


# ---------------------------------------------------------------------------
# Happy path: CLEAN file
# ---------------------------------------------------------------------------

async def test_full_upload_scan_submit_clean(real_service_with_mock_client):
    """Upload → PENDING → webhook CLEAN → status CLEAN → submit returns 201."""
    svc, icm_client = real_service_with_mock_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = make_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: POST /attachments/upload with a valid PDF (< 5MB)
        pdf_content = b"%PDF-1.4 fake pdf content for testing"
        r = await ac.post(
            "/attachments/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text}"
        body = r.json()
        assert "scan_id" in body
        assert "uploaded_at" in body
        assert body["filename"] == "test.pdf"
        scan_id = body["scan_id"]

        # Step 2: GET /attachments/upload/{scan_id}/status → PENDING
        r = await ac.get(f"/attachments/upload/{scan_id}/status", headers=headers)
        assert r.status_code == 200
        status_body = r.json()
        assert status_body["status"] == "PENDING"
        assert status_body["scan_id"] == scan_id

        # Step 3: POST /internal/av-scan-result with status CLEAN
        now = datetime.now(timezone.utc).isoformat()
        r = await ac.post(
            "/internal/av-scan-result",
            json={"scan_id": scan_id, "status": "CLEAN", "scanned_at": now},
            headers={"X-Webhook-Secret": _AV_WEBHOOK_SECRET},
        )
        assert r.status_code == 200

        # Step 4: GET /attachments/upload/{scan_id}/status → CLEAN with scanned_at
        r = await ac.get(f"/attachments/upload/{scan_id}/status", headers=headers)
        assert r.status_code == 200
        status_body = r.json()
        assert status_body["status"] == "CLEAN"
        assert status_body["scanned_at"] is not None

        # Step 5: POST /attachments/sr/{sr_id}/submit → 201
        sr_id = "SR-TEST-001"
        r = await ac.post(
            f"/attachments/sr/{sr_id}/submit",
            json={"scan_id": scan_id, "filename": "test.pdf"},
            headers=headers,
        )
        assert r.status_code == 201, f"Expected 201 but got {r.status_code}: {r.text}"
        submit_body = r.json()
        assert submit_body["sr_id"] == sr_id
        assert submit_body["filename"] == "test.pdf"
        assert "attachment_id" in submit_body

        # Verify ICM client was called with the right sr_id
        icm_client.upload_attachment.assert_awaited_once()
        call_args = icm_client.upload_attachment.call_args
        assert call_args[0][0] == sr_id


# ---------------------------------------------------------------------------
# Infected path
# ---------------------------------------------------------------------------

async def test_submit_infected_file_returns_422(real_service_with_mock_client):
    """Upload → webhook INFECTED → submit returns 422 with 'File failed virus scan'."""
    svc, icm_client = real_service_with_mock_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = make_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Upload file
        pdf_content = b"%PDF-1.4 infected file content"
        r = await ac.post(
            "/attachments/upload",
            files={"file": ("infected.pdf", pdf_content, "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 200
        scan_id = r.json()["scan_id"]

        # Step 2: Post webhook with INFECTED status
        now = datetime.now(timezone.utc).isoformat()
        r = await ac.post(
            "/internal/av-scan-result",
            json={"scan_id": scan_id, "status": "INFECTED", "scanned_at": now},
            headers={"X-Webhook-Secret": _AV_WEBHOOK_SECRET},
        )
        assert r.status_code == 200

        # Step 3: Attempt to submit → 422 with virus scan message
        sr_id = "SR-TEST-002"
        r = await ac.post(
            f"/attachments/sr/{sr_id}/submit",
            json={"scan_id": scan_id, "filename": "infected.pdf"},
            headers=headers,
        )
        assert r.status_code == 422, f"Expected 422 but got {r.status_code}: {r.text}"
        assert "File failed virus scan" in r.json()["detail"]

        # ICM client should never be called for an infected file
        icm_client.upload_attachment.assert_not_awaited()


# ---------------------------------------------------------------------------
# Submit before scan complete
# ---------------------------------------------------------------------------

async def test_submit_before_scan_complete_returns_422(real_service_with_mock_client):
    """Upload → submit immediately (status PENDING) → returns 422 with 'Scan not complete'."""
    svc, icm_client = real_service_with_mock_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = make_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Upload file (status is PENDING — no webhook sent)
        pdf_content = b"%PDF-1.4 pending scan content"
        r = await ac.post(
            "/attachments/upload",
            files={"file": ("pending.pdf", pdf_content, "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 200
        scan_id = r.json()["scan_id"]

        # Verify status is still PENDING
        r = await ac.get(f"/attachments/upload/{scan_id}/status", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "PENDING"

        # Step 2: Attempt to submit before scan completes → 422
        sr_id = "SR-TEST-003"
        r = await ac.post(
            f"/attachments/sr/{sr_id}/submit",
            json={"scan_id": scan_id, "filename": "pending.pdf"},
            headers=headers,
        )
        assert r.status_code == 422, f"Expected 422 but got {r.status_code}: {r.text}"
        assert "Scan not complete" in r.json()["detail"]

        # ICM client should never be called
        icm_client.upload_attachment.assert_not_awaited()
