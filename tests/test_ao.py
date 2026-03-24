"""Tests for AORegistration endpoints (Task 45)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import bcrypt
import pytest
import jwt as pyjwt
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.cache.redis_client import get_redis
from app.dependencies.require_ao_session import (
    clear_ao_sessions,
    get_ao_session,
    set_ao_session,
)
from app.models.ao_registration import AORegistrationSession
from app.routers.admin.ao import _get_ao_registration_service, _get_ao_sr_service
from app.services.ao_registration_service import AORegistrationService, AOLoginError
from app.services.ao_sr_service import AOSRService


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def make_token(
    sub: str = "worker1",
    role: str = "WORKER",
    idir_username: str | None = "jdoe",
    bceid_guid: str | None = None,
    secret: str = "change-me-in-production",
) -> str:
    payload: dict = {"sub": sub, "role": role}
    if idir_username is not None:
        payload["idir_username"] = idir_username
    if bceid_guid is not None:
        payload["bceid_guid"] = bceid_guid
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis():
    """Shared FakeRedis instance for each test."""
    return FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
async def _clear_ao_sessions(fake_redis):
    """Clear Redis AO session store between tests."""
    await clear_ao_sessions(fake_redis)
    yield
    await clear_ao_sessions(fake_redis)


@pytest.fixture
def mock_ao_registration_service():
    """Mock AORegistrationService that succeeds by default."""
    service = MagicMock(spec=AORegistrationService)

    async def _login(sr_number, sin, worker_idir):
        sin_hash = bcrypt.hashpw(sin.encode(), bcrypt.gensalt()).decode()
        now = datetime.now(timezone.utc)
        return AORegistrationSession(
            session_token=uuid4(),
            worker_idir=worker_idir,
            applicant_sr_num=sr_number,
            applicant_sin_hash=sin_hash,
            step_reached=1,
            expires_at=now + timedelta(days=30),
        )

    service.login = AsyncMock(side_effect=_login)
    service.get_step_data = MagicMock(
        return_value={"step": 1, "step_reached": 1, "applicant_sr_num": "SR-001", "data": {}}
    )
    service.advance_step = MagicMock(
        side_effect=lambda session, step: setattr(session, "step_reached", step + 1) or session
    )
    return service


@pytest.fixture
def mock_ao_registration_service_invalid():
    """Mock AORegistrationService that raises AOLoginError."""
    service = MagicMock(spec=AORegistrationService)
    service.login = AsyncMock(side_effect=AOLoginError("Invalid SR number or SIN"))
    return service


@pytest.fixture
def mock_ao_sr_service():
    """Mock AOSRService."""
    service = MagicMock(spec=AOSRService)
    service.submit_ao_form = AsyncMock(
        return_value={
            "sr_id": "SR-001",
            "status": "submitted",
            "submitted_by": "jdoe",
            "applicant_sr_num": "SR-001",
        }
    )
    return service


@pytest.fixture
async def ac(mock_ao_registration_service, mock_ao_sr_service, fake_redis) -> AsyncClient:
    async def _mock_get_redis():
        yield fake_redis

    app.dependency_overrides[_get_ao_registration_service] = lambda: mock_ao_registration_service
    app.dependency_overrides[_get_ao_sr_service] = lambda: mock_ao_sr_service
    app.dependency_overrides[get_redis] = _mock_get_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(_get_ao_registration_service, None)
    app.dependency_overrides.pop(_get_ao_sr_service, None)
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
async def ac_invalid(mock_ao_registration_service_invalid, fake_redis) -> AsyncClient:
    """AsyncClient with service that rejects login."""
    async def _mock_get_redis():
        yield fake_redis

    app.dependency_overrides[_get_ao_registration_service] = (
        lambda: mock_ao_registration_service_invalid
    )
    app.dependency_overrides[get_redis] = _mock_get_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(_get_ao_registration_service, None)
    app.dependency_overrides.pop(get_redis, None)


async def _make_active_session(
    fake_redis,
    token: str | None = None,
    worker_idir: str = "jdoe",
    sr_number: str = "SR-001",
    sin: str = "123456789",
    step_reached: int = 1,
) -> tuple[str, AORegistrationSession]:
    """Helper: create and store an active AO session; returns (token_str, session)."""
    sin_hash = bcrypt.hashpw(sin.encode(), bcrypt.gensalt()).decode()
    session_token = uuid4()
    session = AORegistrationSession(
        session_token=session_token,
        worker_idir=worker_idir,
        applicant_sr_num=sr_number,
        applicant_sin_hash=sin_hash,
        step_reached=step_reached,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    token_str = token or str(session_token)
    await set_ao_session(token_str, session, fake_redis)
    return token_str, session


# ---------------------------------------------------------------------------
# 1. test_ao_login_returns_token
# ---------------------------------------------------------------------------


async def test_ao_login_returns_token(ac, fake_redis):
    """Valid SR+SIN returns 200 with session_token."""
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/ao/login",
        json={"sr_number": "SR-001", "sin": "123456789"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "session_token" in data
    assert "expires_at" in data
    # Token should be stored in session store
    assert await get_ao_session(data["session_token"], fake_redis) is not None


# ---------------------------------------------------------------------------
# 2. test_ao_login_invalid_credentials_returns_403
# ---------------------------------------------------------------------------


async def test_ao_login_invalid_credentials_returns_403(ac_invalid):
    """ICM validation fails -> 403."""
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac_invalid.post(
        "/admin/ao/login",
        json={"sr_number": "INVALID", "sin": "000000000"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 3. test_ao_login_requires_worker_role
# ---------------------------------------------------------------------------


async def test_ao_login_requires_worker_role(ac):
    """CLIENT role -> 403."""
    client_token = make_token(role="CLIENT", idir_username=None)
    response = await ac.post(
        "/admin/ao/login",
        json={"sr_number": "SR-001", "sin": "123456789"},
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. test_ao_session_sin_is_hashed
# ---------------------------------------------------------------------------


async def test_ao_session_sin_is_hashed(ac, fake_redis):
    """Inspect stored session, verify SIN is a bcrypt hash (never plaintext)."""
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    sin = "987654321"
    response = await ac.post(
        "/admin/ao/login",
        json={"sr_number": "SR-002", "sin": sin},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    session_token = response.json()["session_token"]

    stored = await get_ao_session(session_token, fake_redis)
    assert stored is not None

    # Plaintext SIN must NOT be stored
    assert stored.applicant_sin_hash != sin

    # It must be a valid bcrypt hash
    assert bcrypt.checkpw(sin.encode(), stored.applicant_sin_hash.encode())


# ---------------------------------------------------------------------------
# 5. test_ao_registration_step_get_returns_200
# ---------------------------------------------------------------------------


async def test_ao_registration_step_get_returns_200(ac, fake_redis):
    """With valid session, GET step returns 200."""
    token_str, _ = await _make_active_session(fake_redis)
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.get(
        f"/admin/ao/registration/{token_str}/step/1",
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-AO-Session-Token": token_str,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["step"] == 1
    assert "data" in data


# ---------------------------------------------------------------------------
# 6. test_ao_registration_step_post_advances_step
# ---------------------------------------------------------------------------


async def test_ao_registration_step_post_advances_step(ac, mock_ao_registration_service, fake_redis):
    """POST step advances step_reached."""
    token_str, session = await _make_active_session(fake_redis, step_reached=1)
    worker_token = make_token(role="WORKER", idir_username="jdoe")

    response = await ac.post(
        f"/admin/ao/registration/{token_str}/step/1",
        json={},
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-AO-Session-Token": token_str,
        },
    )
    assert response.status_code == 200
    # advance_step was called
    mock_ao_registration_service.advance_step.assert_called_once()


# ---------------------------------------------------------------------------
# 7. test_ao_form_submit_no_pin_required
# ---------------------------------------------------------------------------


async def test_ao_form_submit_no_pin_required(ac, fake_redis):
    """Submit AO form succeeds without a PIN -- worker identity from session is used."""
    token_str, _ = await _make_active_session(fake_redis)
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.post(
        "/admin/ao/form/SR-001/submit",
        json={"field": "value"},
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-AO-Session-Token": token_str,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "submitted"
    # No PIN field required in the response
    assert "pin" not in data


# ---------------------------------------------------------------------------
# 8. test_ao_expired_session_returns_401
# ---------------------------------------------------------------------------


async def test_ao_expired_session_returns_401(ac, fake_redis):
    """Expired session -> 401."""
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    session = AORegistrationSession(
        session_token=uuid4(),
        worker_idir="jdoe",
        applicant_sr_num="SR-001",
        applicant_sin_hash="fakehash",
        step_reached=1,
        expires_at=past_time,
    )
    token_str = str(uuid4())
    await set_ao_session(token_str, session, fake_redis)

    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.get(
        f"/admin/ao/registration/{token_str}/step/1",
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-AO-Session-Token": token_str,
        },
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
    # Expired session should be removed
    assert await get_ao_session(token_str, fake_redis) is None


# ---------------------------------------------------------------------------
# 9. test_ao_ia_applications_returns_200
# ---------------------------------------------------------------------------


async def test_ao_ia_applications_returns_200(ac):
    """Worker can list AO IA applications."""
    worker_token = make_token(role="WORKER", idir_username="jdoe")
    response = await ac.get(
        "/admin/ao/ia-applications",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "applications" in data


# ---------------------------------------------------------------------------
# 10. test_ao_ia_applications_requires_worker_role
# ---------------------------------------------------------------------------


async def test_ao_ia_applications_requires_worker_role(ac):
    """CLIENT role -> 403 for ia-applications."""
    client_token = make_token(role="CLIENT", idir_username=None)
    response = await ac.get(
        "/admin/ao/ia-applications",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert response.status_code == 403
