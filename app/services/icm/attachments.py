from app.services.icm.client import ICMClient


class SiebelAttachmentClient(ICMClient):
    """Siebel REST client for document attachment operations. Covers: D8."""

    async def upload_attachment(self, sr_id: str, file_data: dict) -> dict:
        return await self._post(f"/service-requests/{sr_id}/attachments", json=file_data)

    async def get_attachment(self, attachment_id: str) -> dict:
        return await self._get(f"/attachments/{attachment_id}")

    async def delete_sr_attachment(self, sr_id: str, attachment_id: str) -> dict:
        return await self._delete(f"/service-requests/{sr_id}/attachments/{attachment_id}")

    async def get_message_attachment(self, profile_id: str, msg_id: str, attachment_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/messages/{msg_id}/attachments/{attachment_id}")

    async def get_sr_attachment(self, profile_id: str, sr_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/service-requests/{sr_id}/attachment")
