import structlog
from app.services.icm.employment_plans import SiebelEPClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockEPClient(SiebelEPClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_ep_list(self, profile_id: str) -> dict:
        return data.EP_LISTS.get(profile_id, {"plans": []})

    async def get_ep_detail(self, ep_id: str) -> dict:
        detail = data.EP_DETAILS.get(ep_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_ep_detail", ep_id=ep_id)
        return {"ep_id": ep_id, "status": "SUBMITTED", "plan_date": data._today().isoformat(), "message_deleted": False}

    async def sign_ep(self, ep_id: str, signature_data: dict) -> dict:
        return {"status": "ok", "ep_id": ep_id, "signed_at": data._now().isoformat()}

    async def send_to_icm(self, ep_id: str, pin: str) -> dict:
        return {"status": "ok", "ep_id": ep_id, "sent_at": data._now().isoformat()}

    async def mark_form_submitted(self, ep_id: str, msg_id: int) -> dict:
        return {"status": "ok", "ep_id": ep_id, "msg_id": msg_id}
