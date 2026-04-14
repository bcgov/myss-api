from app.services.icm.registration import SiebelRegistrationClient
from app.services.icm.mock import data


class MockRegistrationClient(SiebelRegistrationClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def register_new_applicant(self, registrant_data: dict) -> dict:
        return data.REGISTRATION_RESPONSES["new"]

    async def register_existing_client(self, link_data: dict) -> dict:
        return data.REGISTRATION_RESPONSES["existing"]

    async def get_link_options(self, bceid_guid: str) -> dict:
        return data.LINK_OPTIONS.get(bceid_guid, {"options": []})
