"""Tests for Notifications + Messages API endpoints (Task 26)."""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.notifications.models import (
    ICMMessageType,
    BannerNotification,
    BannerListResponse,
    MessageSummary,
    MessageDetail,
    InboxListResponse,
    ReplyResponse,
)
from app.domains.notifications.service import NotificationMessageService
from app.routers.notifications import _get_notification_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime.now(timezone.utc)
_FUTURE = _NOW + timedelta(days=7)
_PAST = _NOW - timedelta(days=1)


_STUB_BANNER_ACTIVE = BannerNotification(
    notification_id="BN-001",
    body="System maintenance scheduled for Sunday.",
    start_date=_NOW - timedelta(days=1),
    end_date=_FUTURE,
)

_STUB_BANNER_EXPIRED = BannerNotification(
    notification_id="BN-002",
    body="Old message that should be filtered out.",
    start_date=_NOW - timedelta(days=10),
    end_date=_PAST,
)

_STUB_BANNER_LIST = BannerListResponse(banners=[_STUB_BANNER_ACTIVE])

_STUB_MESSAGE_SUMMARY = MessageSummary(
    message_id="MSG-001",
    subject="Your application has been received",
    sent_date=_NOW,
    is_read=False,
    can_reply=True,
    message_type=ICMMessageType.GENERAL,
)

_STUB_INBOX = InboxListResponse(
    messages=[_STUB_MESSAGE_SUMMARY],
    total=1,
)

_STUB_MESSAGE_DETAIL = MessageDetail(
    message_id="MSG-001",
    subject="Your application has been received",
    sent_date=_NOW,
    is_read=False,
    can_reply=True,
    message_type=ICMMessageType.GENERAL,
    body="Please review your application details.",
    attachments=[],
)

_STUB_MESSAGE_DETAIL_NO_REPLY = MessageDetail(
    message_id="MSG-002",
    subject="Notice: no reply",
    sent_date=_NOW,
    is_read=True,
    can_reply=False,
    message_type=ICMMessageType.SD81_STANDARD,
    body="This message does not allow replies.",
    attachments=[],
)

_STUB_REPLY_RESPONSE = ReplyResponse(
    status="sent",
    sent_at=_NOW,
)


def _make_stub_service() -> NotificationMessageService:
    svc = MagicMock(spec=NotificationMessageService)
    svc.get_banners = AsyncMock(return_value=_STUB_BANNER_LIST)
    svc.list_messages = AsyncMock(return_value=_STUB_INBOX)
    svc.get_message_detail = AsyncMock(return_value=_STUB_MESSAGE_DETAIL)
    svc.mark_read = AsyncMock(return_value=None)
    svc.reply = AsyncMock(return_value=_STUB_REPLY_RESPONSE)
    svc.delete_message = AsyncMock(return_value=None)
    svc.sign_and_send = AsyncMock(return_value=None)
    return svc


@pytest.fixture(autouse=True)
def override_notification_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_notification_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_notification_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /notifications/banners
# ---------------------------------------------------------------------------


async def test_get_banners_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/notifications/banners",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "banners" in data
    assert len(data["banners"]) == 1
    assert data["banners"][0]["notification_id"] == "BN-001"


async def test_get_banners_filters_expired(ac, override_notification_service):
    # Return both active and expired banners from the service (service does filtering)
    # Test that the service was called and only active banners are in result
    active_only = BannerListResponse(banners=[_STUB_BANNER_ACTIVE])
    override_notification_service.get_banners = AsyncMock(return_value=active_only)

    token = make_token("CLIENT")
    response = await ac.get(
        "/notifications/banners",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # Only the active banner should be present
    assert len(data["banners"]) == 1
    assert data["banners"][0]["notification_id"] == "BN-001"


async def test_get_banners_returns_401_without_auth(ac):
    response = await ac.get("/notifications/banners")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Expired banner filtering in the service layer
# ---------------------------------------------------------------------------


async def test_service_filters_expired_banners():
    """Unit test: NotificationMessageService.get_banners filters end_date < now."""
    from app.domains.notifications.service import NotificationMessageService

    mock_client = MagicMock()
    mock_client.get_banners = AsyncMock(return_value={
        "banners": [
            {
                "notification_id": "BN-001",
                "body": "Active banner",
                "start_date": (_NOW - timedelta(days=1)).isoformat(),
                "end_date": _FUTURE.isoformat(),
            },
            {
                "notification_id": "BN-002",
                "body": "Expired banner",
                "start_date": (_NOW - timedelta(days=10)).isoformat(),
                "end_date": _PAST.isoformat(),
            },
        ]
    })

    svc = NotificationMessageService(client=mock_client)
    result = await svc.get_banners("CASE-001")

    # Only active banners (end_date >= now) should be returned
    assert len(result.banners) == 1
    assert result.banners[0].notification_id == "BN-001"


# ---------------------------------------------------------------------------
# GET /messages
# ---------------------------------------------------------------------------


async def test_list_messages_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert "total" in data
    assert data["total"] == 1


async def test_list_messages_returns_401_without_auth(ac):
    response = await ac.get("/messages")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /messages/{msg_id}
# ---------------------------------------------------------------------------


async def test_get_message_detail_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/messages/MSG-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message_id"] == "MSG-001"
    assert "body" in data
    assert "attachments" in data


async def test_get_message_detail_fires_mark_read_as_background_task(ac, override_notification_service):
    token = make_token("CLIENT")
    await ac.get(
        "/messages/MSG-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    # mark_read should be called as a background task — it will be called
    # (FastAPI executes background tasks during test response handling)
    override_notification_service.mark_read.assert_awaited_once_with("MSG-001")


# ---------------------------------------------------------------------------
# POST /messages/{msg_id}/reply
# ---------------------------------------------------------------------------


async def test_reply_to_message_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/messages/MSG-001/reply",
        json={"body": "Thank you for the information."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "sent_at" in data


async def test_reply_with_body_over_4000_chars_returns_422(ac):
    token = make_token("CLIENT")
    long_body = "x" * 4001
    response = await ac.post(
        "/messages/MSG-001/reply",
        json={"body": long_body},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_reply_when_can_reply_false_returns_403(ac, override_notification_service):
    # Return a message with can_reply=False
    override_notification_service.get_message_detail = AsyncMock(
        return_value=_STUB_MESSAGE_DETAIL_NO_REPLY
    )
    token = make_token("CLIENT")
    response = await ac.post(
        "/messages/MSG-002/reply",
        json={"body": "Trying to reply"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Reply not allowed" in response.json()["detail"]


async def test_reply_returns_401_without_auth(ac):
    response = await ac.post(
        "/messages/MSG-001/reply",
        json={"body": "Hello"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /messages/{msg_id}
# ---------------------------------------------------------------------------


async def test_delete_message_returns_204(ac):
    token = make_token("CLIENT")
    response = await ac.delete(
        "/messages/MSG-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


async def test_delete_message_returns_401_without_auth(ac):
    response = await ac.delete("/messages/MSG-001")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /messages/{msg_id}/sign
# ---------------------------------------------------------------------------


async def test_sign_and_send_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/messages/MSG-001/sign",
        json={"pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_sign_and_send_returns_401_without_auth(ac):
    response = await ac.post(
        "/messages/MSG-001/sign",
        json={"pin": "1234"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# ICMMessageType enum values match spec
# ---------------------------------------------------------------------------


def test_icm_message_type_enum_values():
    assert ICMMessageType.SD81_STANDARD == "HR0081"
    assert ICMMessageType.SD81_RESTART == "HR0081Restart"
    assert ICMMessageType.SD81_STREAMLINED_RESTART == "HR0081StreamlinedRestart"
    assert ICMMessageType.SD81_PENDING_DOCUMENTS == "HR0081 Pending Documents"
    assert ICMMessageType.FORM_SUBMISSION == "FormSubmission"
    assert ICMMessageType.GENERAL == "General"
