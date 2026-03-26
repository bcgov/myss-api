import structlog
from app.services.icm.profile import SiebelProfileClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockProfileClient(SiebelProfileClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_tombstone(self, bceid_guid: str) -> dict:
        return data.TOMBSTONES.get(bceid_guid, data.TOMBSTONES[data.ALICE_BCEID])

    async def validate_pin(self, bceid_guid: str, pin: str) -> dict:
        return {"status": "ok", "valid": True}

    async def update_tombstone(self, bceid_guid: str, data: dict) -> dict:
        return {"status": "ok", "bceid_guid": bceid_guid, **data}

    async def get_profile(self, bceid_guid: str) -> dict:
        return data.PROFILE_DATA.get(bceid_guid, data.PROFILE_DATA[data.ALICE_BCEID])

    async def link_profile(self, bceid_guid: str, link_data: dict) -> dict:
        return {"status": "ok", "bceid_guid": bceid_guid, "linked": True}

    async def has_newer_profile(self, bceid_guid: str) -> dict:
        return {"has_newer": False}

    async def get_banners(self, case_number: str) -> dict:
        resolved = data.resolve_case_number(case_number)
        return data.BANNERS.get(resolved, {"banners": []})
