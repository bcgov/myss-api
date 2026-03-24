import hmac
import io
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.domains.attachments.models import (
    AttachmentSubmitRequest,
    AttachmentSubmitResponse,
    ScanResultWebhookRequest,
    ScanStatusResponse,
    UploadResponse,
)
from app.domains.attachments.service import AttachmentService
from app.services.icm.deps import get_siebel_attachment_client
from app.services.icm.exceptions import ICMServiceUnavailableError

attachment_router = APIRouter(tags=["attachments"])

_MAX_FILE_SIZE = 5_242_880  # 5 MB

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _get_attachment_service() -> AttachmentService:
    return AttachmentService(client=get_siebel_attachment_client())


def _sanitize_filename(filename: str) -> str:
    """Keep only alphanumeric, dot, hyphen, and underscore characters."""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    name = name.strip("_")
    return name or "attachment"


def _require_webhook_secret(x_webhook_secret: str = Header(None)):
    """Validate the shared secret for internal webhooks."""
    expected = os.getenv("AV_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(status_code=500, detail="AV_WEBHOOK_SECRET not configured")
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


# ---------------------------------------------------------------------------
# POST /attachments/upload
# ---------------------------------------------------------------------------


@attachment_router.post("/attachments/upload", response_model=UploadResponse, status_code=200)
async def upload_file(
    file: UploadFile = File(...),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AttachmentService = Depends(_get_attachment_service),
) -> UploadResponse:
    if not file.content_type or file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="File type not allowed.")
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size of 5 MB.")
    return await svc.upload(filename=file.filename or "upload", content=content, user_id=user.user_id)


# ---------------------------------------------------------------------------
# GET /attachments/upload/{scan_id}/status
# ---------------------------------------------------------------------------


@attachment_router.get("/attachments/upload/{scan_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(
    scan_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AttachmentService = Depends(_get_attachment_service),
) -> ScanStatusResponse:
    try:
        return await svc.get_scan_status(scan_id, user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /internal/av-scan-result  (shared-secret auth — internal webhook)
# ---------------------------------------------------------------------------


@attachment_router.post("/internal/av-scan-result", status_code=200)
async def av_scan_result(
    body: ScanResultWebhookRequest,
    _: None = Depends(_require_webhook_secret),
    svc: AttachmentService = Depends(_get_attachment_service),
):
    try:
        await svc.process_scan_result(body.scan_id, body.status, body.scanned_at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "updated"}


# ---------------------------------------------------------------------------
# POST /attachments/sr/{sr_id}/submit
# ---------------------------------------------------------------------------


@attachment_router.post("/attachments/sr/{sr_id}/submit", response_model=AttachmentSubmitResponse, status_code=201)
async def submit_attachment(
    sr_id: str,
    body: AttachmentSubmitRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AttachmentService = Depends(_get_attachment_service),
) -> AttachmentSubmitResponse:
    try:
        return await svc.submit_attachment(sr_id=sr_id, scan_id=body.scan_id, filename=body.filename, user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ICMServiceUnavailableError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again later.")


# ---------------------------------------------------------------------------
# GET /attachments/sr/{sr_id}/download
# ---------------------------------------------------------------------------


@attachment_router.get("/attachments/sr/{sr_id}/download")
async def download_sr_attachment(
    sr_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AttachmentService = Depends(_get_attachment_service),
):
    try:
        content, filename = await svc.download_sr_attachment(profile_id=user.user_id, sr_id=sr_id)
    except ICMServiceUnavailableError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again later.")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{_sanitize_filename(filename)}"'},
    )


# ---------------------------------------------------------------------------
# GET /attachments/messages/{msg_id}/{attachment_id}/download
# ---------------------------------------------------------------------------


@attachment_router.get("/attachments/messages/{msg_id}/{attachment_id}/download")
async def download_message_attachment(
    msg_id: str,
    attachment_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AttachmentService = Depends(_get_attachment_service),
):
    try:
        content, filename = await svc.download_message_attachment(
            profile_id=user.user_id, msg_id=msg_id, attachment_id=attachment_id
        )
    except ICMServiceUnavailableError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again later.")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{_sanitize_filename(filename)}"'},
    )
