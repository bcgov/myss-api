from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.domains.account.pin_service import PINService
from app.services.icm.deps import get_siebel_notification_client, get_siebel_account_client
from app.domains.notifications.models import (
    BannerListResponse,
    InboxListResponse,
    MessageDetail,
    ReplyRequest,
    ReplyResponse,
    SignRequest,
)
from app.domains.notifications.service import NotificationMessageService

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
messages_router = APIRouter(prefix="/messages", tags=["messages"])


def _get_notification_service() -> NotificationMessageService:
    pin_svc = PINService(client=get_siebel_account_client())
    return NotificationMessageService(client=get_siebel_notification_client(), pin_service=pin_svc)


# ---------------------------------------------------------------------------
# Banners
# ---------------------------------------------------------------------------


@notifications_router.get("/banners", response_model=BannerListResponse)
async def get_banners(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> BannerListResponse:
    return await svc.get_banners(user.user_id)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@messages_router.get("", response_model=InboxListResponse)
async def list_messages(
    page: int = Query(1, ge=1),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> InboxListResponse:
    return await svc.list_messages(profile_id=user.user_id, page=page)


@messages_router.get("/{msg_id}", response_model=MessageDetail)
async def get_message_detail(
    msg_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> MessageDetail:
    detail = await svc.get_message_detail(msg_id)
    background_tasks.add_task(svc.mark_read, msg_id)
    return detail


@messages_router.post("/{msg_id}/reply", response_model=ReplyResponse)
async def reply_to_message(
    msg_id: str,
    request: ReplyRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> ReplyResponse:
    message = await svc.get_message_detail(msg_id)
    if not message.can_reply:
        raise HTTPException(status_code=403, detail="Reply not allowed")
    return await svc.reply(msg_id, request, message.can_reply)


@messages_router.delete("/{msg_id}", status_code=204)
async def delete_message(
    msg_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
):
    await svc.delete_message(msg_id)
    return None


@messages_router.post("/{msg_id}/sign", status_code=200)
async def sign_and_send(
    msg_id: str,
    request: SignRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
):
    # PINValidationError → 403 and ICMServiceUnavailableError → 503
    # are handled by global exception handlers in app/exception_handlers.py
    await svc.sign_and_send(
        msg_id=msg_id,
        pin=request.pin,
        bceid_guid=user.bceid_guid or user.user_id,
    )
    return {"status": "signed"}
