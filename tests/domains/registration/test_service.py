# tests/domains/registration/test_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.domains.registration.service import RegistrationService
from app.domains.registration.models import (
    AccountCreationType,
    RegistrationStep,
    RegistrationSessionState,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def svc(mock_session, mock_redis):
    return RegistrationService(session=mock_session, redis=mock_redis)


async def test_start_registration_returns_token(svc, mock_session):
    """start_registration creates a RegistrationSession row and returns a UUID token."""
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    token = await svc.start_registration(
        account_creation_type=AccountCreationType.SELF,
    )
    assert token is not None
    assert len(token) == 36  # UUID format
    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


async def test_get_session_by_token_returns_state(svc, mock_session):
    """get_session_by_token returns RegistrationSessionState for a valid token."""
    mock_row = MagicMock()
    mock_row.token = "test-token-uuid"
    mock_row.account_creation_type = "SELF"
    mock_row.step_reached = 1
    mock_row.poa_data = None
    mock_row.registrant_data = None
    mock_row.spouse_data = None
    mock_row.pin_hash = None
    mock_row.invite_token = None
    mock_row.invite_token_used = False
    mock_row.pin_salt = None
    mock_row.user_id = None
    mock_row.expires_at = datetime(2099, 1, 1, tzinfo=timezone.utc)

    result = MagicMock()
    result.fetchone = MagicMock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=result)

    state = await svc.get_session_by_token("test-token-uuid")
    assert state is not None
    assert state.token == "test-token-uuid"
    assert state.step_reached == 1


async def test_get_session_by_token_returns_none_for_missing(svc, mock_session):
    """get_session_by_token returns None when token not found."""
    result = MagicMock()
    result.fetchone = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=result)

    state = await svc.get_session_by_token("nonexistent-token")
    assert state is None


async def test_advance_step_updates_step_reached(svc, mock_session):
    """advance_step issues an UPDATE and commits."""
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await svc.advance_step("test-token", to_step=2)
    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


async def test_generate_invite_token_is_unique(svc):
    """generate_invite_token produces a non-empty UUID string."""
    t1 = svc._generate_invite_token()
    t2 = svc._generate_invite_token()
    assert t1 != t2
    assert len(t1) == 36


async def test_hash_pin_is_not_plaintext(svc):
    """hash_pin returns a value that is not the original PIN."""
    hashed, salt = svc.hash_pin("1234")
    assert hashed != "1234"
    assert len(salt) > 0


async def test_verify_pin_correct(svc):
    """verify_pin returns True when PIN matches stored hash."""
    hashed, salt = svc.hash_pin("5678")
    assert svc.verify_pin("5678", hashed, salt) is True


async def test_verify_pin_wrong(svc):
    """verify_pin returns False when PIN does not match."""
    hashed, salt = svc.hash_pin("5678")
    assert svc.verify_pin("9999", hashed, salt) is False


async def test_advance_step_raises_for_missing_token(svc, mock_session):
    """advance_step raises ValueError when session token not found."""
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    with pytest.raises(ValueError, match="not found"):
        await svc.advance_step("nonexistent-token", to_step=2)
    mock_session.commit.assert_not_awaited()


async def test_consume_invite_token_returns_session_token(svc, mock_session):
    """consume_invite_token atomically marks token used and returns session token."""
    mock_row = MagicMock()
    mock_row.token = "session-token-123"
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    result = await svc.consume_invite_token("invite-uuid")
    assert result == "session-token-123"
    mock_session.commit.assert_awaited_once()


async def test_consume_invite_token_returns_none_when_not_found(svc, mock_session):
    """consume_invite_token returns None when invite token not found or already used."""
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    result = await svc.consume_invite_token("bad-invite-uuid")
    assert result is None
    mock_session.commit.assert_not_awaited()
