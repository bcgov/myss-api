from app.services.icm.client import ICMClient


class SiebelEPClient(ICMClient):
    """Siebel REST client for employment plan operations. Covers: D6."""

    async def get_ep_list(self, profile_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/employment-plans")

    async def get_ep_detail(self, ep_id: str) -> dict:
        return await self._get(f"/employment-plans/{ep_id}")

    async def sign_ep(self, ep_id: str, signature_data: dict) -> dict:
        return await self._post(f"/employment-plans/{ep_id}/sign", json=signature_data)

    async def send_to_icm(self, ep_id: str, pin: str) -> dict:
        return await self._post(f"/employment-plans/{ep_id}/send", json={"pin": pin})

    async def mark_form_submitted(self, ep_id: str, msg_id: int) -> dict:
        return await self._post(f"/employment-plans/{ep_id}/mark-submitted", json={"msg_id": msg_id})
