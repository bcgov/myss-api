# tests/integration/test_registration_flow.py
"""
Full registration flow integration test.

Tests the complete sequence:
  POST /registration/start
  -> POST /registration/{token}/personal-info
  -> POST /registration/{token}/pin
  -> GET  /registration/verify/{invite_token}   (simulated)

Uses the test client fixture with patched RegistrationService to avoid
requiring PostgreSQL or Redis in CI.

Note: steps 5 (BCeID OIDC redirect) and 6 (link-bceid) are not covered
here as the link-bceid endpoint is a stub pending Auth.js integration.
"""
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.domains.registration.models import (
    AccountCreationType,
    RegistrationSessionState,
)

_TOKEN = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
_INVITE = "test-invite-uuid-12345"


def _mock_state(step: int, invite_used: bool = False) -> RegistrationSessionState:
    return RegistrationSessionState(
        token=_TOKEN,
        account_creation_type=AccountCreationType.SELF,
        step_reached=step,
        invite_token_used=invite_used,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


async def test_full_registration_flow_self(client: AsyncClient):
    """Walk through all API steps of a self-registration flow."""

    # Step 1: Start registration
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.start_registration = AsyncMock(return_value=_TOKEN)

        start_resp = await client.post(
            "/registration/start",
            json={"account_creation_type": "SELF"},
        )
    assert start_resp.status_code == 201
    token = start_resp.json()["token"]
    assert token == _TOKEN
    assert len(token) == 36

    # Step 2: Save personal info
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=_mock_state(step=1))
        instance.save_registrant_data = AsyncMock()
        instance.issue_invite_token = AsyncMock(return_value=_INVITE)

        personal_resp = await client.post(
            f"/registration/{token}/personal-info",
            json={
                "first_name": "Mary",
                "last_name": "Smith",
                "email": "mary@example.com",
                "email_confirm": "mary@example.com",
                "sin": "046454286",
                "date_of_birth": "1990-05-15",
                "gender": "F",
                "phone_number": "2505551234",
                "phone_type": "CELL",
                "has_open_case": False,
            },
        )
    assert personal_resp.status_code == 200
    assert personal_resp.json()["next_step"] == 3

    # Step 3: Consume invite token (simulate email link click)
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.consume_invite_token = AsyncMock(return_value=token)

        verify_resp = await client.get(
            f"/registration/verify/{_INVITE}",
            follow_redirects=False,
        )
    assert verify_resp.status_code in (302, 307)
    assert token in verify_resp.headers.get("location", "")

    # Step 4: Save PIN
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(
            return_value=_mock_state(step=4, invite_used=True),
        )
        instance.save_pin = AsyncMock()

        pin_resp = await client.post(
            f"/registration/{token}/pin",
            json={"pin": "4321", "pin_confirm": "4321"},
        )
    assert pin_resp.status_code == 200
    assert pin_resp.json()["next_step"] == 5


async def test_registration_token_not_found(client: AsyncClient):
    """Accessing a step with an invalid token returns 404."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=None)

        response = await client.get("/registration/nonexistent-token-xyz/step/2")
    assert response.status_code == 404


async def test_registration_email_mismatch_rejected(client: AsyncClient):
    """Step 2 rejects mismatched email/email_confirm."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(return_value=_mock_state(step=1))

        resp = await client.post(
            f"/registration/{_TOKEN}/personal-info",
            json={
                "first_name": "Mary",
                "last_name": "Smith",
                "email": "mary@example.com",
                "email_confirm": "OTHER@example.com",
                "sin": "046454286",
                "date_of_birth": "1990-05-15",
                "gender": "F",
                "phone_number": "2505551234",
                "phone_type": "CELL",
                "has_open_case": False,
            },
        )
    assert resp.status_code == 422


async def test_invite_token_single_use_enforced(client: AsyncClient):
    """Verify that a consumed invite token returns 410 on second use."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.consume_invite_token = AsyncMock(return_value=None)

        resp = await client.get("/registration/verify/already-used-token")
    assert resp.status_code == 410


async def test_pin_mismatch_rejected(client: AsyncClient):
    """Step 4 rejects mismatched PIN/pin_confirm at the Pydantic layer."""
    with patch("app.routers.registration.RegistrationService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_session_by_token = AsyncMock(
            return_value=_mock_state(step=4, invite_used=True),
        )

        resp = await client.post(
            f"/registration/{_TOKEN}/pin",
            json={"pin": "1234", "pin_confirm": "9999"},
        )
    assert resp.status_code == 422
