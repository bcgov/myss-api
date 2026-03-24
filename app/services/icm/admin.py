from app.services.icm.client import ICMClient


class SiebelAdminClient(ICMClient):
    """Siebel REST client for admin/worker support operations. Covers: D10."""

    async def search_profiles(
        self,
        first_name: str | None,
        last_name: str | None,
        sin: str | None,
        page: int,
    ) -> dict:
        params: dict = {"page": page, "page_size": 10}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if sin:
            params["sin"] = sin
        return await self._get("/admin/clients", params=params)

    async def get_client_profile(self, client_bceid_guid: str) -> dict:
        return await self._get(f"/admin/clients/{client_bceid_guid}")

    async def get_worker_permissions(self, idir_username: str) -> dict:
        return await self._get(f"/admin/workers/{idir_username}/permissions")

    async def validate_ao_login(self, sr_number: str, sin: str) -> dict:
        """Validate AO login credentials (SR number + SIN) against ICM.

        Returns applicant info dict on success, or raises an exception on failure.
        Stub implementation — returns mock applicant data for now.
        """
        # TODO: Replace with real ICM call when endpoint is available
        # e.g. return await self._post("/admin/ao/validate", json={"sr_number": sr_number, "sin": sin})
        # For stub: always return a valid applicant dict (callers should mock this in tests)
        return {
            "sr_number": sr_number,
            "applicant_name": "Stub Applicant",
            "case_status": "Active",
        }
