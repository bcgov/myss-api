from app.services.icm.client import ICMClient


class SiebelSRClient(ICMClient):
    """Siebel REST client for service request operations. Covers: D2."""

    async def create_sr(self, sr_type: str, profile_id: str) -> dict:
        return await self._post("/service-requests", json={"sr_type": sr_type, "profile_id": profile_id})

    async def get_sr_list(self, profile_id: str) -> dict:
        return await self._get("/service-requests", params={"profile_id": profile_id})

    async def get_sr_detail(self, sr_id: str) -> dict:
        return await self._get(f"/service-requests/{sr_id}")

    async def cancel_sr(self, sr_id: str, reason: str) -> dict:
        return await self._post(f"/service-requests/{sr_id}/cancel", json={"reason": reason})

    async def get_return_action(self, sr_type: str) -> dict:
        return await self._get("/service-requests/return-action", params={"sr_type": sr_type})

    async def get_eligible_types(self, profile_id: str, case_status: str) -> dict:
        return await self._get("/service-requests/eligible-types", params={"profile_id": profile_id, "case_status": case_status})

    async def finalize_sr_form(self, sr_id: str, answers: dict) -> dict:
        return await self._post(f"/service-requests/{sr_id}/finalize", json={"answers": answers})
