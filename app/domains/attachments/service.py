import base64
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.attachments.models import (
    AttachmentSubmitResponse,
    ScanStatus,
    ScanStatusResponse,
    UploadResponse,
)

# Module-level scan job store shared across service instances (would be DB in production)
_scan_jobs: dict[str, dict] = {}


class AttachmentService:
    def __init__(self, client):
        self._client = client

    async def upload(self, filename: str, content: bytes, user_id: str) -> UploadResponse:
        scan_id = str(uuid4())
        now = datetime.now(timezone.utc)
        _scan_jobs[scan_id] = {
            "scan_id": scan_id,
            "filename": filename,
            "status": ScanStatus.PENDING,
            "content": content,
            "user_id": user_id,
            "uploaded_at": now,
            "scanned_at": None,
        }
        return UploadResponse(scan_id=scan_id, filename=filename, uploaded_at=now)

    async def get_scan_status(self, scan_id: str, user_id: str) -> ScanStatusResponse:
        job = _scan_jobs.get(scan_id)
        if not job or job["user_id"] != user_id:
            raise ValueError("Scan job not found")
        return ScanStatusResponse(scan_id=scan_id, status=job["status"], scanned_at=job.get("scanned_at"))

    async def process_scan_result(self, scan_id: str, status: ScanStatus, scanned_at: datetime) -> None:
        job = _scan_jobs.get(scan_id)
        if not job:
            raise ValueError("Scan job not found")
        job["status"] = status
        job["scanned_at"] = scanned_at

    async def submit_attachment(self, sr_id: str, scan_id: str, filename: str, user_id: str) -> AttachmentSubmitResponse:
        job = _scan_jobs.get(scan_id)
        if not job or job["user_id"] != user_id:
            raise ValueError("Scan job not found")
        if job["status"] in (ScanStatus.PENDING, ScanStatus.SCANNING):
            raise ValueError("Scan not complete")
        if job["status"] == ScanStatus.INFECTED:
            raise ValueError("File failed virus scan")
        content_b64 = base64.b64encode(job["content"]).decode()
        result = await self._client.upload_attachment(sr_id, {
            "filename": filename,
            "content_base64": content_b64,
        })
        return AttachmentSubmitResponse(
            attachment_id=result.get("attachment_id", scan_id),
            sr_id=sr_id,
            filename=filename,
        )

    async def download_message_attachment(self, profile_id: str, msg_id: str, attachment_id: str) -> tuple[bytes, str]:
        data = await self._client.get_message_attachment(profile_id, msg_id, attachment_id)
        return data.get("content", b""), data.get("filename", "attachment")

    async def download_sr_attachment(self, profile_id: str, sr_id: str) -> tuple[bytes, str]:
        data = await self._client.get_sr_attachment(profile_id, sr_id)
        return data.get("content", b""), data.get("filename", "attachment")
