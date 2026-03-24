import pytest
import respx
import httpx
from app.services.icm.client import ICMClient
from app.services.icm.exceptions import ICMServiceUnavailableError, ICMCaseNotFoundError
from app.services.icm.error_mapping import map_icm_error


@pytest.fixture
def icm_config():
    return {
        "base_url": "https://icm.example.gov.bc.ca",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "token_url": "https://icm.example.gov.bc.ca/oauth/token",
    }


@pytest.mark.asyncio
@respx.mock
async def test_token_refreshed_when_expired(icm_config):
    """OAuth2 token is fetched when first request is made."""
    token_route = respx.post(icm_config["token_url"]).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    respx.get(f"{icm_config['base_url']}/test").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )

    client = ICMClient(**icm_config)
    await client._get("/test")

    assert token_route.called


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_500(icm_config):
    """Retries 3 times on 500 responses."""
    respx.post(icm_config["token_url"]).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, json={"error": "server error"})
        return httpx.Response(200, json={"result": "ok"})

    respx.get(f"{icm_config['base_url']}/test").mock(side_effect=side_effect)

    client = ICMClient(**icm_config, _test_no_wait=True)
    result = await client._get("/test")
    assert call_count == 3
    assert result["result"] == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_circuit_opens_after_five_failures(icm_config):
    """Circuit breaker opens after 5 consecutive failures."""
    respx.post(icm_config["token_url"]).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    respx.get(f"{icm_config['base_url']}/test").mock(
        return_value=httpx.Response(500, json={"error": "server error"})
    )

    client = ICMClient(**icm_config, circuit_failure_threshold=5, _test_no_wait=True)
    # Each call retries 3x internally; 5 open-circuit triggers = 15 total 500s
    for _ in range(5):
        try:
            await client._get("/test")
        except Exception:
            pass

    with pytest.raises(ICMServiceUnavailableError):
        await client._get("/test")


def test_map_icm_error_case_not_found():
    exc = map_icm_error({"errorCode": "ICM_ERR_NO_CASE", "message": "No case found"})
    assert isinstance(exc, ICMCaseNotFoundError)


def test_map_icm_error_revoked():
    from app.services.icm.exceptions import ICMAccessRevokedError
    exc = map_icm_error({"errorCode": "ICM_ERR_REVOKED", "message": "Access revoked"})
    assert isinstance(exc, ICMAccessRevokedError)


def test_map_icm_error_no_contact():
    from app.services.icm.exceptions import ICMContactNotFoundError
    exc = map_icm_error({"errorCode": "ICM_ERR_NO_CONTACT", "message": "No contact"})
    assert isinstance(exc, ICMContactNotFoundError)


def test_map_icm_error_multi_contacts():
    from app.services.icm.exceptions import ICMMultipleContactsError
    exc = map_icm_error({"errorCode": "ICM_ERR_MULTI_CONTACTS", "message": "Multiple contacts"})
    assert isinstance(exc, ICMMultipleContactsError)


def test_map_icm_error_closed_case():
    from app.services.icm.exceptions import ICMClosedCaseError
    exc = map_icm_error({"errorCode": "ICM_ERR_CLOSED_CASE", "message": "Closed case"})
    assert isinstance(exc, ICMClosedCaseError)


def test_map_icm_error_unknown_falls_back_to_base():
    from app.services.icm.exceptions import ICMError
    exc = map_icm_error({"errorCode": "ICM_ERR_UNKNOWN_XYZ", "message": "Unknown"})
    assert isinstance(exc, ICMError)
