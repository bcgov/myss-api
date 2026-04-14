from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.services.icm.deps import get_siebel_account_client
from app.domains.account.models import (
    PINValidateRequest,
    PINChangeRequest,
    PINResetRequest,
    PINResetConfirmRequest,
)
from app.domains.account.pin_service import PINService

pin_router = APIRouter(prefix="/auth/pin", tags=["pin"])


def _get_pin_service() -> PINService:
    return PINService(client=get_siebel_account_client())


@pin_router.post("/validate", status_code=200)
async def validate_pin(
    request: PINValidateRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PINService = Depends(_get_pin_service),
):
    valid = await svc.validate(user.user_id, request.pin)
    if not valid:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    return {"status": "valid"}


@pin_router.post("/change", status_code=200)
async def change_pin(
    request: PINChangeRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PINService = Depends(_get_pin_service),
):
    try:
        await svc.change_pin(user.user_id, request.current_pin, request.new_pin)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"status": "changed"}


@pin_router.post("/reset-request", status_code=202)
async def reset_request(
    request: PINResetRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PINService = Depends(_get_pin_service),
):
    await svc.request_reset(user.user_id, request.email)
    return {"status": "accepted"}


@pin_router.post("/reset-confirm", status_code=200)
async def reset_confirm(
    request: PINResetConfirmRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PINService = Depends(_get_pin_service),
):
    try:
        await svc.confirm_reset(request.token, request.new_pin)
    except ValueError as e:
        raise HTTPException(status_code=410, detail=str(e))
    return {"status": "reset"}
