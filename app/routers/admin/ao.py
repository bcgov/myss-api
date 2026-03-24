"""AO (Admin Override) Registration endpoints."""

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.auth.models import UserContext
from app.cache.redis_client import get_redis
from app.dependencies.require_ao_session import (
    require_ao_session,
    set_ao_session,
)
from app.dependencies.require_worker_role import require_worker_role
from app.models.ao_registration import (
    AOLoginRequest,
    AORegistrationSession,
    AORegistrationStep,
    AOSessionToken,
)
from app.services.ao_registration_service import AOLoginError, AORegistrationService
from app.services.ao_sr_service import AOSRService
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.deps import get_siebel_admin_client

ao_router = APIRouter(prefix="/admin/ao", tags=["admin"])


# ---------------------------------------------------------------------------
# Dependency factories (overrideable in tests)
# ---------------------------------------------------------------------------


def _get_admin_client() -> SiebelAdminClient:
    return get_siebel_admin_client()


def _get_ao_registration_service() -> AORegistrationService:
    return AORegistrationService(admin_client=_get_admin_client())


def _get_ao_sr_service() -> AOSRService:
    return AOSRService(admin_client=_get_admin_client())


def _verify_session_ownership(
    session: AORegistrationSession, user: UserContext
) -> None:
    """Ensure the authenticated worker owns this AO session."""
    if session.worker_idir != user.idir_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session belongs to a different worker",
        )


# ---------------------------------------------------------------------------
# 1. POST /admin/ao/login
# ---------------------------------------------------------------------------


@ao_router.post("/login", response_model=AOSessionToken)
async def ao_login(
    body: AOLoginRequest,
    user: UserContext = Depends(require_worker_role),
    ao_service: AORegistrationService = Depends(_get_ao_registration_service),
    redis: aioredis.Redis = Depends(get_redis),
) -> AOSessionToken:
    """Create an AO registration session by validating SR number + SIN against ICM."""
    try:
        session = await ao_service.login(
            sr_number=body.sr_number,
            sin=body.sin,
            worker_idir=user.idir_username or user.user_id,
        )
    except AOLoginError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid SR number or SIN",
        ) from exc

    token_str = str(session.session_token)
    await set_ao_session(token_str, session, redis)

    return AOSessionToken(
        session_token=token_str,
        expires_at=session.expires_at,
    )


# ---------------------------------------------------------------------------
# 2. GET /admin/ao/registration/{token}/step/{step}
# ---------------------------------------------------------------------------


@ao_router.get(
    "/registration/{token}/step/{step}",
    response_model=AORegistrationStep,
)
async def get_registration_step(
    token: str,
    step: int,
    session: AORegistrationSession = Depends(require_ao_session),
    user: UserContext = Depends(require_worker_role),
    ao_service: AORegistrationService = Depends(_get_ao_registration_service),
) -> AORegistrationStep:
    """Return data for the given registration step."""
    _verify_session_ownership(session, user)
    step_data = ao_service.get_step_data(session, step)
    return AORegistrationStep(step=step, data=step_data)


# ---------------------------------------------------------------------------
# 3. POST /admin/ao/registration/{token}/step/{step}
# ---------------------------------------------------------------------------


@ao_router.post(
    "/registration/{token}/step/{step}",
    response_model=AORegistrationStep,
)
async def submit_registration_step(
    token: str,
    step: int,
    body: dict[str, Any] = Body(default={}),
    session: AORegistrationSession = Depends(require_ao_session),
    user: UserContext = Depends(require_worker_role),
    ao_service: AORegistrationService = Depends(_get_ao_registration_service),
    redis: aioredis.Redis = Depends(get_redis),
) -> AORegistrationStep:
    """Submit a registration step and advance step_reached."""
    _verify_session_ownership(session, user)
    updated_session = ao_service.advance_step(session, step)
    # Persist using the session's own token as key (not the path param)
    await set_ao_session(str(updated_session.session_token), updated_session, redis)
    return AORegistrationStep(step=step, data={"step_reached": updated_session.step_reached})


# ---------------------------------------------------------------------------
# 4. POST /admin/ao/form/{sr_id}/submit
# ---------------------------------------------------------------------------


@ao_router.post("/form/{sr_id}/submit")
async def submit_ao_form(
    sr_id: str,
    body: dict[str, Any] = Body(default={}),
    session: AORegistrationSession = Depends(require_ao_session),
    user: UserContext = Depends(require_worker_role),
    ao_sr_service: AOSRService = Depends(_get_ao_sr_service),
) -> dict:
    """Submit an AO dynamic form. No PIN required -- worker identity from session is used."""
    _verify_session_ownership(session, user)
    result = await ao_sr_service.submit_ao_form(
        sr_id=sr_id,
        form_data=body,
        session=session,
    )
    return result


# ---------------------------------------------------------------------------
# 5. GET /admin/ao/ia-applications
# ---------------------------------------------------------------------------


@ao_router.get("/ia-applications")
async def list_ia_applications(
    user: UserContext = Depends(require_worker_role),
) -> dict:
    """List AO IA applications. Requires worker role."""
    return {"applications": []}
