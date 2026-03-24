from app.services.icm.client import ICMClient


class SiebelAccountClient(ICMClient):
    async def get_profile(self, user_id: str) -> dict:
        return await self._get(f"/profiles/{user_id}")

    async def update_contact(self, user_id: str, data: dict) -> dict:
        return await self._put(f"/profiles/{user_id}/contact", json=data)

    async def get_case_members(self, user_id: str) -> dict:
        return await self._get(f"/profiles/{user_id}/case-members")

    async def sync_profile(self, user_id: str) -> dict:
        return await self._post(f"/profiles/{user_id}/sync")

    async def validate_pin(self, user_id: str, pin: str) -> dict:
        return await self._post(f"/profiles/{user_id}/validate-pin", json={"pin": pin})

    async def change_pin(self, user_id: str, new_pin: str) -> dict:
        return await self._post(f"/profiles/{user_id}/change-pin", json={"new_pin": new_pin})

    async def request_pin_reset(self, user_id: str, email: str) -> dict:
        return await self._post(f"/profiles/{user_id}/reset-pin", json={"email": email})

    async def confirm_pin_reset(self, token: str, new_pin: str) -> dict:
        return await self._post("/pin-reset/confirm", json={"token": token, "new_pin": new_pin})
