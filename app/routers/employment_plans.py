from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.services.icm.deps import get_siebel_ep_client
from app.domains.employment_plans.models import (
    EPListResponse, EPDetailResponse, EPSignRequest, EPSignResponse,
)
from app.domains.employment_plans.service import EmploymentPlanService

ep_router = APIRouter(prefix="/employment-plans", tags=["employment-plans"])


def _get_ep_service() -> EmploymentPlanService:
    return EmploymentPlanService(client=get_siebel_ep_client())


@ep_router.get("", response_model=EPListResponse)
async def list_employment_plans(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: EmploymentPlanService = Depends(_get_ep_service),
) -> EPListResponse:
    return await svc.list_plans(user.user_id)


@ep_router.get("/{ep_id}", response_model=EPDetailResponse)
async def get_employment_plan_detail(
    ep_id: int,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: EmploymentPlanService = Depends(_get_ep_service),
) -> EPDetailResponse:
    return await svc.get_detail(str(ep_id))


@ep_router.post("/{ep_id}/sign", response_model=EPSignResponse)
async def sign_employment_plan(
    ep_id: int,
    request: EPSignRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: EmploymentPlanService = Depends(_get_ep_service),
) -> EPSignResponse:
    try:
        return await svc.sign_and_send(
            ep_id=str(ep_id),
            pin=request.pin,
            message_id=request.message_id,
            profile_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
