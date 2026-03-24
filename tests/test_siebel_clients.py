import pytest
import respx
import httpx
from app.services.icm.profile import SiebelProfileClient
from app.services.icm.registration import SiebelRegistrationClient
from app.services.icm.service_requests import SiebelSRClient
from app.services.icm.exceptions import ICMCaseNotFoundError


ICM_BASE = "https://icm.example.gov.bc.ca"
TOKEN_URL = f"{ICM_BASE}/oauth/token"
CLIENT_KWARGS = {
    "base_url": ICM_BASE,
    "client_id": "test",
    "client_secret": "secret",
    "token_url": TOKEN_URL,
}


def mock_token():
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "expires_in": 3600}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_profile_get_tombstone_happy_path():
    mock_token()
    respx.get(f"{ICM_BASE}/contacts/bceid-123/tombstone").mock(
        return_value=httpx.Response(200, json={"contact_id": "C001", "full_name": "Test User"})
    )
    client = SiebelProfileClient(**CLIENT_KWARGS)
    result = await client.get_tombstone("bceid-123")
    assert result["contact_id"] == "C001"


@pytest.mark.asyncio
@respx.mock
async def test_profile_get_tombstone_not_found_raises():
    mock_token()
    respx.get(f"{ICM_BASE}/contacts/bad-guid/tombstone").mock(
        return_value=httpx.Response(
            404, json={"errorCode": "ICM_ERR_NO_CASE", "message": "No case"}
        )
    )
    client = SiebelProfileClient(**CLIENT_KWARGS)
    with pytest.raises(ICMCaseNotFoundError):
        await client.get_tombstone("bad-guid")


@pytest.mark.asyncio
@respx.mock
async def test_registration_register_new_applicant():
    mock_token()
    respx.post(f"{ICM_BASE}/registrations/new").mock(
        return_value=httpx.Response(200, json={"registration_id": "R001", "status": "PENDING"})
    )
    client = SiebelRegistrationClient(**CLIENT_KWARGS)
    result = await client.register_new_applicant({"bceid_guid": "g1", "sin": "000000000"})
    assert result["registration_id"] == "R001"


@pytest.mark.asyncio
@respx.mock
async def test_sr_client_create_sr():
    mock_token()
    respx.post(f"{ICM_BASE}/service-requests").mock(
        return_value=httpx.Response(200, json={"sr_number": "SR-001", "status": "OPEN"})
    )
    client = SiebelSRClient(**CLIENT_KWARGS)
    result = await client.create_sr("ASSIST", "PROFILE-001")
    assert result["sr_number"] == "SR-001"


@pytest.mark.asyncio
@respx.mock
async def test_error_propagates_from_sr_client():
    mock_token()
    respx.post(f"{ICM_BASE}/service-requests").mock(
        return_value=httpx.Response(
            404, json={"errorCode": "ICM_ERR_NO_CASE", "message": "Profile not found"}
        )
    )
    client = SiebelSRClient(**CLIENT_KWARGS)
    with pytest.raises(ICMCaseNotFoundError):
        await client.create_sr("ASSIST", "BAD-PROFILE")
