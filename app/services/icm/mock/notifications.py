import structlog
from app.services.icm.notifications import SiebelNotificationClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockNotificationClient(SiebelNotificationClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_banners(self, case_number: str) -> dict:
        resolved = data.resolve_case_number(case_number)
        return data.BANNERS.get(resolved, {"banners": []})

    async def get_messages(self, profile_id: str, page: int = 1) -> dict:
        resolved = data.resolve_profile_id(profile_id)
        return data.MESSAGES.get(resolved, {"messages": [], "total": 0})

    async def get_message_detail(self, message_id: str) -> dict:
        detail = data.MESSAGE_DETAILS.get(message_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_message_detail", message_id=message_id)
        return {"message_id": message_id, "subject": "Unknown", "body": "Mock message not found", "sent_date": data._now().isoformat(), "is_read": True, "can_reply": False, "message_type": "GENERAL", "attachments": []}

    async def mark_read(self, message_id: str) -> dict:
        return {"status": "ok", "message_id": message_id}

    async def send_message(self, message_data: dict) -> dict:
        return {"status": "ok", "message_id": f"MSG-NEW-{data.uuid4().hex[:6]}"}

    async def delete_message(self, msg_id: str) -> dict:
        return {"status": "ok", "message_id": msg_id}

    async def sign_and_send(self, msg_id: str, pin: str) -> dict:
        return {"status": "ok", "message_id": msg_id, "signed_at": data._now().isoformat()}
