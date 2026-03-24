# app/routers/registration.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.db.session import get_session
from app.cache.redis_client import get_redis
from app.domains.registration.models import (
    AccountCreationType,
    RegistrationSessionState,
)
from app.domains.registration.service import RegistrationService
from app.domains.registration.schemas import (
    StartRegistrationRequest,
    StartRegistrationResponse,
    PersonalInfoRequest,
    PersonalInfoResponse,
    PinRequest,
    PinResponse,
    StepStateResponse,
)

router = APIRouter(prefix="/registration", tags=["registration"])


def _get_svc(
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> RegistrationService:
    return RegistrationService(session=session, redis=redis)


async def _require_session(
    token: str,
    svc: RegistrationService = Depends(_get_svc),
) -> RegistrationSessionState:
    state = await svc.get_session_by_token(token)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration session not found or expired",
        )
    return state


# ---------------------------------------------------------------------------
# Step 1: Start registration
# ---------------------------------------------------------------------------
@router.post("/start", response_model=StartRegistrationResponse, status_code=201)
async def start_registration(
    body: StartRegistrationRequest,
    svc: RegistrationService = Depends(_get_svc),
) -> StartRegistrationResponse:
    """Create a new registration session. Returns a session token.

    The token must be included in all subsequent step URLs.
    No authentication required — registration is a public flow.
    """
    token = await svc.start_registration(
        account_creation_type=body.account_creation_type,
    )
    return StartRegistrationResponse(token=token)


# ---------------------------------------------------------------------------
# Step 3: Email verification — invite token consumption
# (Must be registered BEFORE /{token}/... routes to avoid 'verify' matching as token)
# ---------------------------------------------------------------------------
@router.get("/verify/{invite_token}")
async def verify_email(
    invite_token: str,
    svc: RegistrationService = Depends(_get_svc),
) -> RedirectResponse:
    """Consume an invite token from the verification email (BR-D1-09).

    Redirects the applicant to step 4 (PIN creation).
    Returns 410 Gone if the token is expired, used, or not found.
    """
    session_token = await svc.consume_invite_token(invite_token)
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This verification link has expired or has already been used",
        )
    return RedirectResponse(
        url=f"/registration/{session_token}/pin",
        status_code=status.HTTP_302_FOUND,
    )


# ---------------------------------------------------------------------------
# Step state reader (for resume / UI state restoration)
# ---------------------------------------------------------------------------
@router.get("/{token}/step/{step_number}", response_model=StepStateResponse)
async def get_step_state(
    step_number: int,
    state: RegistrationSessionState = Depends(_require_session),
) -> StepStateResponse:
    """Return the current state of a registration session for a given step."""
    return StepStateResponse(
        token=state.token,
        step_reached=state.step_reached,
        account_creation_type=state.account_creation_type,
    )


# ---------------------------------------------------------------------------
# Step 2: Personal information
# ---------------------------------------------------------------------------
@router.post("/{token}/personal-info", response_model=PersonalInfoResponse)
async def save_personal_info(
    token: str,
    data: PersonalInfoRequest,
    background_tasks: BackgroundTasks,
    state: RegistrationSessionState = Depends(_require_session),
    svc: RegistrationService = Depends(_get_svc),
) -> PersonalInfoResponse:
    """Save applicant personal information (step 2).

    Validates SIN (Luhn), PHN (MOD 11 if provided), age (>=16), email match.
    Triggers email verification as a background task after save.
    """
    # Guard: step 1 (session creation) must be complete. Since start_registration
    # sets step_reached = 1 immediately, this is always true when a valid session
    # exists. The guard exists to enforce the invariant explicitly.
    if state.step_reached < 1:
        raise HTTPException(status_code=409, detail="Previous steps must be completed first")
    await svc.save_registrant_data(
        state.token,
        data.model_dump(exclude={"email_confirm", "spouse"}, exclude_none=True),
        spouse_data=data.spouse.model_dump() if data.spouse else None,
    )
    # TODO(Phase 2 Auth): After issue_invite_token generates the token,
    # dispatch verification email via MailJet/Celery (Domain 4, Task 27).
    # Currently the invite token is stored but no email is sent.
    background_tasks.add_task(svc.issue_invite_token, state.token)
    return PersonalInfoResponse(next_step=3)


# ---------------------------------------------------------------------------
# Step 4: PIN creation
# ---------------------------------------------------------------------------
@router.post("/{token}/pin", response_model=PinResponse)
async def save_pin(
    token: str,
    body: PinRequest,
    state: RegistrationSessionState = Depends(_require_session),
    svc: RegistrationService = Depends(_get_svc),
) -> PinResponse:
    """Hash and persist the applicant's PIN (step 4). BR-D1-10."""
    if state.step_reached < 4:
        raise HTTPException(status_code=409, detail="Email verification must be completed first")
    await svc.save_pin(token=state.token, pin=body.pin)
    return PinResponse(next_step=5)


# ---------------------------------------------------------------------------
# Step 5/6: BCeID link and registration completion
# (Full implementation in Task 16 — SiebelRegistrationClient integration)
# ---------------------------------------------------------------------------
@router.post("/{token}/link-bceid", status_code=202)
async def link_bceid(
    token: str,
    state: RegistrationSessionState = Depends(_require_session),
) -> dict:
    """Placeholder for BCeID link step. Full implementation in Task 16."""
    if state.step_reached < 5:
        raise HTTPException(status_code=409, detail="Previous steps must be completed first")
    return {"status": "pending", "message": "BCeID link not yet implemented"}
