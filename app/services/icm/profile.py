from app.services.icm.client import ICMClient


class SiebelProfileClient(ICMClient):
    """Siebel REST client for profile and tombstone operations. Covers: D1, D7, D10."""

    async def get_tombstone(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/tombstone")

    async def validate_pin(self, bceid_guid: str, pin: str) -> dict:
        return await self._post(f"/contacts/{bceid_guid}/validate-pin", json={"pin": pin})

    async def update_tombstone(self, bceid_guid: str, data: dict) -> dict:
        return await self._put(f"/contacts/{bceid_guid}/tombstone", json=data)

    async def get_profile(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/profile")

    async def link_profile(self, bceid_guid: str, link_data: dict) -> dict:
        return await self._post(f"/contacts/{bceid_guid}/link", json=link_data)

    async def has_newer_profile(self, bceid_guid: str) -> dict:
        return await self._get(f"/contacts/{bceid_guid}/has-newer-profile")

    async def get_banners(self, case_number: str) -> dict:
        # NOTE: Canonical owner is SiebelNotificationClient.get_banners(). See step-3 arch doc.
        return await self._get(f"/cases/{case_number}/banners")
