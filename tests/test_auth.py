import pytest
from httpx import AsyncClient, ASGITransport
import jwt as pyjwt
from datetime import datetime, timedelta, UTC
from app.main import app
from app.auth.dependencies import get_current_user, _get_jwt_secret
from app.auth.models import UserContext, UserRole


def make_token(role: str, secret: str | None = None, algorithm: str = "HS256", **extra) -> str:
    if secret is None:
        secret = _get_jwt_secret()
    payload = {
        "sub": "test-user-id",
        "role": role,
        "bceid_guid": "test-bceid-guid",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **extra,
    }
    return pyjwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
async def ac():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_missing_token_returns_401(ac):
    """Any protected route should return 401 without a token."""
    response = await ac.get("/account/profile")
    assert response.status_code == 401


async def test_invalid_token_returns_401(ac):
    """A token signed with the wrong secret should return 401."""
    token = make_token("CLIENT", secret="wrong-secret")
    response = await ac.get(
        "/account/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_get_current_user_returns_user_context():
    """Directly test get_current_user with a valid token."""
    from fastapi.security import HTTPAuthorizationCredentials

    token = make_token("CLIENT")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds)
    assert user.user_id == "test-user-id"
    assert user.role == UserRole.CLIENT
    assert user.bceid_guid == "test-bceid-guid"


async def test_get_current_user_rejects_wrong_role_format():
    """get_current_user should reject tokens with invalid role values."""
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    secret = _get_jwt_secret()
    bad_token = pyjwt.encode(
        {"sub": "u1", "role": "INVALID_ROLE", "exp": datetime.now(UTC) + timedelta(hours=1)},
        secret,
        algorithm="HS256",
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad_token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds)
    assert exc_info.value.status_code == 401
