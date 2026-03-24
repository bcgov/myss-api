class PINService:
    def __init__(self, client):
        self._client = client

    async def validate(self, user_id: str, pin: str) -> bool:
        result = await self._client.validate_pin(user_id, pin)
        return result.get("valid", False)

    async def change_pin(self, user_id: str, current_pin: str, new_pin: str) -> None:
        valid = await self.validate(user_id, current_pin)
        if not valid:
            raise ValueError("Current PIN is incorrect")
        await self._client.change_pin(user_id, new_pin)

    async def request_reset(self, user_id: str, email: str) -> None:
        await self._client.request_pin_reset(user_id, email)

    async def confirm_reset(self, token: str, new_pin: str) -> None:
        result = await self._client.confirm_pin_reset(token, new_pin)
        if not result.get("success", False):
            raise ValueError("Token is invalid or expired")
