import structlog
from app.services.icm.account import SiebelAccountClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAccountClient(SiebelAccountClient):
    def __init__(self):
        pass  # skip parent's HTTP/OAuth setup

    async def aclose(self) -> None:
        pass  # no HTTP client to close

    async def get_profile(self, user_id: str) -> dict:
        profile = data.ACCOUNT_PROFILES.get(user_id)
        if profile:
            return profile
        logger.warning("mock_unknown_id", method="get_profile", user_id=user_id)
        return dict(data.ACCOUNT_PROFILES[data.ALICE_USER_ID], user_id=user_id)

    async def update_contact(self, user_id: str, data: dict) -> dict:
        return {"status": "ok", "user_id": user_id, **data}

    async def get_case_members(self, user_id: str) -> dict:
        return data.CASE_MEMBERS.get(user_id, data.CASE_MEMBERS[data.ALICE_USER_ID])

    async def sync_profile(self, user_id: str) -> dict:
        return {"status": "ok", "user_id": user_id}

    async def validate_pin(self, user_id: str, pin: str) -> dict:
        return {"status": "ok", "valid": True}

    async def change_pin(self, user_id: str, new_pin: str) -> dict:
        return {"status": "ok"}

    async def request_pin_reset(self, user_id: str, email: str) -> dict:
        return {"status": "ok", "message": "PIN reset email sent"}

    async def confirm_pin_reset(self, token: str, new_pin: str) -> dict:
        return {"status": "ok", "message": "PIN has been reset"}
