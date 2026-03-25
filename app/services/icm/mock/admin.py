import structlog
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAdminClient(SiebelAdminClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def search_profiles(self, first_name: str | None, last_name: str | None, sin: str | None, page: int) -> dict:
        # Simple filter: if a name is provided, filter results
        results = data.ADMIN_SEARCH_RESULTS["results"]
        if first_name:
            results = [r for r in results if first_name.lower() in r["full_name"].lower()]
        if last_name:
            results = [r for r in results if last_name.lower() in r["full_name"].lower()]
        return {"results": results, "total": len(results), "page": page, "page_size": 10}

    async def get_client_profile(self, client_bceid_guid: str) -> dict:
        return data.ADMIN_CLIENT_PROFILES.get(client_bceid_guid, data.ADMIN_CLIENT_PROFILES[data.ALICE_BCEID])

    async def get_worker_permissions(self, idir_username: str) -> dict:
        return data.WORKER_PERMISSIONS.get(idir_username, {"idir_username": idir_username, "permissions": []})

    async def validate_ao_login(self, sr_number: str, sin: str) -> dict:
        return {"sr_number": sr_number, "applicant_name": "Alice Thompson", "case_status": "Active"}
