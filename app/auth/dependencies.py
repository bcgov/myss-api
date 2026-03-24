import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt as pyjwt
from jwt.exceptions import PyJWTError
from app.auth.models import UserContext, UserRole

security = HTTPBearer(auto_error=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
JWT_ALGORITHM = "HS256"

_INSECURE_DEFAULTS = {"change-me-in-production", "secret", ""}

# Lazy-loaded JWT secret — read from env at first use, not at import time.
_JWT_SECRET: str | None = None


def _get_jwt_secret() -> str:
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
    return _JWT_SECRET


def validate_jwt_config() -> None:
    """Call at startup. Raises RuntimeError if JWT_SECRET is insecure in non-local environments."""
    secret = _get_jwt_secret()
    if ENVIRONMENT not in ("local", "test") and secret in _INSECURE_DEFAULTS:
        raise RuntimeError(
            f"JWT_SECRET must be set to a secure value in environment '{ENVIRONMENT}'. "
            "Set the JWT_SECRET environment variable."
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    secret = _get_jwt_secret()
    try:
        payload = pyjwt.decode(
            credentials.credentials,
            secret,
            algorithms=[JWT_ALGORITHM],
        )
        return UserContext(
            user_id=payload["sub"],
            role=UserRole(payload["role"]),
            bceid_guid=payload.get("bceid_guid"),
            idir_username=payload.get("idir_username"),
        )
    except (PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_role(required_role: UserRole):
    async def _require(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role != required_role and not (
            required_role == UserRole.WORKER and user.role == UserRole.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required; caller has '{user.role}'",
            )
        return user

    return _require
