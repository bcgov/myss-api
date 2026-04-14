import structlog
from app.services.icm.service_requests import SiebelSRClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockSRClient(SiebelSRClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def create_sr(self, sr_type: str, profile_id: str) -> dict:
        new_id = f"SR-NEW-{data.uuid4().hex[:6]}"
        return {"sr_id": new_id, "sr_type": sr_type, "sr_number": new_id, "status": "Open", "created_at": data._now().isoformat()}

    async def get_sr_list(self, profile_id: str) -> dict:
        resolved = data.resolve_profile_id(profile_id)
        return data.SR_LISTS.get(resolved, {"items": [], "total": 0, "page": 1, "page_size": 10})

    async def get_sr_detail(self, sr_id: str) -> dict:
        detail = data.SR_DETAILS.get(sr_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_sr_detail", sr_id=sr_id)
        return {"sr_id": sr_id, "sr_type": "ASSIST", "sr_number": sr_id, "status": "Open", "client_name": "Unknown", "created_at": data._now().isoformat(), "answers": {}, "attachments": []}

    async def cancel_sr(self, sr_id: str, reason: str) -> dict:
        return {"status": "ok", "sr_id": sr_id, "new_status": "Cancelled"}

    async def get_return_action(self, sr_type: str) -> dict:
        return data.SR_RETURN_ACTIONS.get(sr_type, {"sr_type": sr_type, "action": "submit", "requires_pin": True})

    async def get_eligible_types(self, profile_id: str, case_status: str) -> dict:
        return data.ELIGIBLE_SR_TYPES.get(case_status, {"types": []})

    async def finalize_sr_form(self, sr_id: str, answers: dict) -> dict:
        return {"status": "ok", "sr_id": sr_id}
