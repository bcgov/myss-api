from datetime import datetime, timezone

import structlog

from app.services.icm.notifications import SiebelNotificationClient
from app.domains.account.pin_service import PINService
from app.domains.notifications.models import (
    BannerNotification,
    BannerListResponse,
    MessageSummary,
    MessageDetail,
    InboxListResponse,
    ReplyRequest,
    ReplyResponse,
    ICMMessageType,
)


logger = structlog.get_logger()


class NotificationMessageService:
    def __init__(self, client: SiebelNotificationClient, pin_service: PINService | None = None):
        self._client = client
        self._pin_service = pin_service

    async def get_banners(self, case_number: str) -> BannerListResponse:
        raw = await self._client.get_banners(case_number)
        now = datetime.now(timezone.utc)
        banners = []
        for item in raw.get("banners", []):
            banner = BannerNotification(**item)
            # Filter out expired banners
            if banner.end_date >= now:
                banners.append(banner)
        return BannerListResponse(banners=banners)

    async def list_messages(self, profile_id: str, page: int = 1) -> InboxListResponse:
        raw = await self._client.get_messages(profile_id, page)
        messages = [MessageSummary(**item) for item in raw.get("messages", [])]
        total = raw.get("total", len(messages))
        return InboxListResponse(messages=messages, total=total)

    async def get_message_detail(self, msg_id: str) -> MessageDetail:
        raw = await self._client.get_message_detail(msg_id)
        return MessageDetail(**raw)

    async def mark_read(self, msg_id: str) -> None:
        """Mark a message as read. Failures are logged; background task continues."""
        try:
            await self._client.mark_read(msg_id)
        except Exception as exc:
            logger.warning(
                "notifications_mark_read_failed",
                msg_id=msg_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async def reply(self, msg_id: str, request: ReplyRequest, can_reply: bool) -> ReplyResponse:
        if not can_reply:
            raise ValueError("Reply not allowed for this message")
        raw = await self._client.send_message({
            "reply_to": msg_id,
            "body": request.body,
            "attachment_ids": request.attachment_ids,
        })
        return ReplyResponse(
            status=raw.get("status", "sent"),
            sent_at=raw.get("sent_at", datetime.now(timezone.utc)),
        )

    async def delete_message(self, msg_id: str) -> None:
        await self._client.delete_message(msg_id)

    async def sign_and_send(self, msg_id: str, pin: str, bceid_guid: str) -> None:
        from app.services.icm.exceptions import PINValidationError

        if not self._pin_service:
            raise RuntimeError("PINService not configured")
        if not await self._pin_service.validate(bceid_guid, pin):
            raise PINValidationError("Invalid PIN")
        await self._client.sign_and_send(msg_id, pin)
