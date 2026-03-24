from app.services.icm.client import ICMClient


class SiebelRegistrationClient(ICMClient):
    """Siebel REST client for registration workflow. Covers: D1."""

    async def register_new_applicant(self, registrant_data: dict) -> dict:
        return await self._post("/registrations/new", json=registrant_data)

    async def register_existing_client(self, link_data: dict) -> dict:
        return await self._post("/registrations/existing", json=link_data)

    async def get_link_options(self, bceid_guid: str) -> dict:
        return await self._get(f"/registrations/link-options/{bceid_guid}")
