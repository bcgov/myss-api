from app.services.icm.client import ICMClient


class SiebelNotificationClient(ICMClient):
    """Siebel REST client for inbox messages and banners. Covers: D4."""

    async def get_banners(self, case_number: str) -> dict:
        return await self._get(f"/cases/{case_number}/banners")

    async def get_messages(self, profile_id: str, page: int = 1) -> dict:
        return await self._get("/messages", params={"profile_id": profile_id, "page": page})

    async def get_message_detail(self, message_id: str) -> dict:
        return await self._get(f"/messages/{message_id}")

    async def mark_read(self, message_id: str) -> dict:
        return await self._post(f"/messages/{message_id}/mark-read")

    async def send_message(self, message_data: dict) -> dict:
        return await self._post("/messages", json=message_data)

    async def delete_message(self, msg_id: str) -> dict:
        return await self._delete(f"/messages/{msg_id}")

    async def sign_and_send(self, msg_id: str, pin: str) -> dict:
        return await self._post(f"/messages/{msg_id}/sign", json={"pin": pin})
