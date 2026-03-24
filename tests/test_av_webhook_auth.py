"""Tests for AV webhook shared-secret authentication (Task 4)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.domains.attachments.service import AttachmentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_service() -> AttachmentService:
    svc = MagicMock(spec=AttachmentService)
    svc.process_scan_result = AsyncMock(return_value=None)
    return svc


AV_WEBHOOK_SECRET = "test-secret-123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables before the app is imported."""
    monkeypatch.setenv("AV_WEBHOOK_SECRET", AV_WEBHOOK_SECRET)
    monkeypatch.setenv("ICM_BASE_URL", "https://test.example.com")
    monkeypatch.setenv("ICM_CLIENT_ID", "test")
    monkeypatch.setenv("ICM_CLIENT_SECRET", "test")
    monkeypatch.setenv("ICM_TOKEN_URL", "https://test.example.com/token")


@pytest.fixture(autouse=True)
def _override_attachment_service():
    from app.main import app
    from app.routers.attachments import _get_attachment_service

    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_attachment_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_attachment_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _scan_result_payload() -> dict:
    return {
        "scan_id": "job-123",
        "status": "CLEAN",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_av_webhook_returns_401_without_secret_header(ac):
    """Request without X-Webhook-Secret header should be rejected."""
    response = await ac.post("/internal/av-scan-result", json=_scan_result_payload())
    assert response.status_code == 401


async def test_av_webhook_returns_401_with_wrong_secret(ac):
    """Request with incorrect X-Webhook-Secret should be rejected."""
    response = await ac.post(
        "/internal/av-scan-result",
        json=_scan_result_payload(),
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


async def test_av_webhook_succeeds_with_correct_secret(ac, _override_attachment_service):
    """Request with the correct X-Webhook-Secret should pass auth."""
    response = await ac.post(
        "/internal/av-scan-result",
        json=_scan_result_payload(),
        headers={"X-Webhook-Secret": AV_WEBHOOK_SECRET},
    )
    # Should be 200 (success) not 401 (auth failure)
    assert response.status_code == 200
    _override_attachment_service.process_scan_result.assert_awaited_once()
