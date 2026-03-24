# tests/test_registration_routes.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock


async def test_start_registration_returns_token(client: AsyncClient):
    """POST /registration/start returns a session token."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.start_registration = AsyncMock(return_value="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        response = await client.post(
            "/registration/start",
            json={"account_creation_type": "SELF"},
        )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["token"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


async def test_start_registration_invalid_type(client: AsyncClient):
    """POST /registration/start rejects unknown account_creation_type."""
    response = await client.post(
        "/registration/start",
        json={"account_creation_type": "INVALID_TYPE"},
    )
    assert response.status_code == 422


async def test_get_step_returns_current_state(client: AsyncClient):
    """GET /registration/{token}/step/{n} returns the current step state."""
    from app.domains.registration.models import AccountCreationType, RegistrationSessionState
    from datetime import datetime, timezone

    mock_state = RegistrationSessionState(
        token="test-token",
        account_creation_type=AccountCreationType.SELF,
        step_reached=2,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=mock_state)

        response = await client.get("/registration/test-token/step/2")
    assert response.status_code == 200
    data = response.json()
    assert data["step_reached"] == 2
    assert data["token"] == "test-token"


async def test_get_step_404_for_missing_token(client: AsyncClient):
    """GET /registration/{token}/step/{n} returns 404 when token not found."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=None)

        response = await client.get("/registration/nonexistent/step/1")
    assert response.status_code == 404


async def test_save_personal_info(client: AsyncClient):
    """POST /registration/{token}/personal-info persists step 2 data."""
    from app.domains.registration.models import AccountCreationType, RegistrationSessionState
    from datetime import datetime, timezone

    mock_state = RegistrationSessionState(
        token="tok",
        account_creation_type=AccountCreationType.SELF,
        step_reached=1,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=mock_state)
        instance.save_registrant_data = AsyncMock()
        instance.issue_invite_token = AsyncMock()

        response = await client.post(
            "/registration/tok/personal-info",
            json={
                "first_name": "Mary",
                "middle_name": "",
                "last_name": "Smith",
                "email": "mary@example.com",
                "email_confirm": "mary@example.com",
                "sin": "046454286",
                "phn": "",
                "date_of_birth": "1990-05-15",
                "gender": "F",
                "phone_number": "2505551234",
                "phone_type": "CELL",
                "has_open_case": False,
            },
        )
    assert response.status_code == 200


async def test_save_personal_info_email_mismatch(client: AsyncClient):
    """POST /registration/{token}/personal-info returns 422 when email != email_confirm."""
    from app.domains.registration.models import AccountCreationType, RegistrationSessionState
    from datetime import datetime, timezone

    mock_state = RegistrationSessionState(
        token="tok",
        account_creation_type=AccountCreationType.SELF,
        step_reached=1,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=mock_state)

        response = await client.post(
            "/registration/tok/personal-info",
            json={
                "first_name": "Mary",
                "middle_name": "",
                "last_name": "Smith",
                "email": "mary@example.com",
                "email_confirm": "different@example.com",
                "sin": "046454286",
                "phn": "",
                "date_of_birth": "1990-05-15",
                "gender": "F",
                "phone_number": "2505551234",
                "phone_type": "CELL",
                "has_open_case": False,
            },
        )
    assert response.status_code == 422


async def test_verify_invite_token_consumes_token(client: AsyncClient):
    """GET /registration/verify/{invite_token} consumes the invite token and redirects."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.consume_invite_token = AsyncMock(return_value="session-token-123")

        response = await client.get(
            "/registration/verify/some-invite-uuid",
            follow_redirects=False,
        )
    # Expect redirect to step 4 page
    assert response.status_code in (302, 307)
    assert "session-token-123" in response.headers.get("location", "")


async def test_verify_invite_token_410_if_invalid(client: AsyncClient):
    """GET /registration/verify/{invite_token} returns 410 Gone for expired/used tokens."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.consume_invite_token = AsyncMock(return_value=None)

        response = await client.get("/registration/verify/bad-token")
    assert response.status_code == 410


async def test_save_pin(client: AsyncClient):
    """POST /registration/{token}/pin saves a valid 4-digit PIN."""
    from app.domains.registration.models import AccountCreationType, RegistrationSessionState
    from datetime import datetime, timezone

    mock_state = RegistrationSessionState(
        token="tok",
        account_creation_type=AccountCreationType.SELF,
        step_reached=4,
        invite_token_used=True,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=mock_state)
        instance.save_pin = AsyncMock()

        response = await client.post(
            "/registration/tok/pin",
            json={"pin": "4321", "pin_confirm": "4321"},
        )
    assert response.status_code == 200
