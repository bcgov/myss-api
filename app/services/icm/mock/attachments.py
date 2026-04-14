import structlog
from app.services.icm.attachments import SiebelAttachmentClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAttachmentClient(SiebelAttachmentClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def upload_attachment(self, sr_id: str, file_data: dict) -> dict:
        att_id = f"ATT-NEW-{data.uuid4().hex[:6]}"
        return {"attachment_id": att_id, "sr_id": sr_id, "filename": file_data.get("filename", "uploaded.pdf"), "uploaded_at": data._now().isoformat()}

    async def get_attachment(self, attachment_id: str) -> dict:
        return data.ATTACHMENT_METADATA.get(attachment_id, {"attachment_id": attachment_id, "filename": "unknown.pdf", "mime_type": "application/pdf", "size_bytes": 0, "uploaded_at": data._now().isoformat()})

    async def delete_sr_attachment(self, sr_id: str, attachment_id: str) -> dict:
        return {"status": "ok", "sr_id": sr_id, "attachment_id": attachment_id}

    async def get_message_attachment(self, profile_id: str, msg_id: str, attachment_id: str) -> dict:
        return data.ATTACHMENT_METADATA.get(attachment_id, {"attachment_id": attachment_id, "filename": "message_attachment.pdf", "mime_type": "application/pdf", "size_bytes": 0})

    async def get_sr_attachment(self, profile_id: str, sr_id: str) -> dict:
        return {"sr_id": sr_id, "profile_id": profile_id, "attachments": []}
