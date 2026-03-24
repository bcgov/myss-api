from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.db.session import get_session
from app.domains.account.pin_service import PINService
from app.services.icm.deps import get_siebel_sr_client, get_siebel_account_client
from app.services.icm.exceptions import ICMActiveSRConflictError, ICMSRAlreadyWithdrawnError, ICMError, ICMServiceUnavailableError
from app.domains.service_requests.models import (
    SRListResponse,
    SRTypeMetadata,
    SRCreateRequest,
    SRDraftResponse,
    DynamicFormSchema,
    SRFormUpdateRequest,
    SRSubmitRequest,
    SRSubmitResponse,
    SRDetailResponse,
    SRWithdrawRequest,
    SRType,
)
from app.domains.service_requests.service import ServiceRequestService

router = APIRouter(prefix="/service-requests", tags=["service-requests"])


def _get_sr_service(session: AsyncSession = Depends(get_session)) -> ServiceRequestService:
    pin_svc = PINService(client=get_siebel_account_client())
    return ServiceRequestService(sr_client=get_siebel_sr_client(), session=session, pin_service=pin_svc)


@router.get("", response_model=SRListResponse)
async def list_service_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRListResponse:
    return await svc.list_srs(profile_id=user.user_id, page=page, page_size=page_size)


@router.get("/eligible-types", response_model=list[SRTypeMetadata])
async def get_eligible_types(
    case_status: str = Query(...),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> list[SRTypeMetadata]:
    return await svc.get_eligible_types(profile_id=user.user_id, case_status=case_status)


@router.post("", response_model=SRDraftResponse, status_code=201)
async def create_service_request(
    request: SRCreateRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRDraftResponse:
    try:
        return await svc.create_sr(
            sr_type=request.sr_type,
            profile_id=user.user_id,
            user_id=user.user_id,
        )
    except ICMActiveSRConflictError:
        raise HTTPException(
            status_code=409,
            detail="An active service request of this type already exists",
        )
    except ICMServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable. Please try again later.",
        )


@router.get("/{sr_id}/draft", response_model=SRDraftResponse)
async def get_draft(
    sr_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRDraftResponse:
    draft = await svc.get_draft(sr_id, user_id=user.user_id)
    if not draft:
        raise HTTPException(status_code=404, detail="SR draft not found")
    return draft


@router.get("/{sr_id}/form", response_model=DynamicFormSchema)
async def get_form_schema(
    sr_id: str,
    sr_type: SRType = Query(...),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> DynamicFormSchema:
    schema = await svc.get_form_schema(sr_id, sr_type=sr_type)
    if not schema:
        raise HTTPException(status_code=404, detail="No form schema for this SR type")
    return schema


@router.put("/{sr_id}/form", response_model=SRDraftResponse)
async def update_form_draft(
    sr_id: str,
    request: SRFormUpdateRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRDraftResponse:
    draft = await svc.save_form_draft(sr_id, request.answers, request.page_index, user_id=user.user_id)
    if not draft:
        raise HTTPException(status_code=404, detail="SR draft not found")
    return draft


@router.post("/{sr_id}/submit", response_model=SRSubmitResponse)
async def submit_service_request(
    sr_id: str,
    request: SRSubmitRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRSubmitResponse:
    # PINValidationError → 403 and ICMServiceUnavailableError → 503
    # are handled by global exception handlers in app/exception_handlers.py
    return await svc.submit_sr(
        sr_id=sr_id,
        pin=request.pin,
        spouse_pin=request.spouse_pin,
        bceid_guid=user.bceid_guid or user.user_id,
        user_id=user.user_id,
    )


@router.get("/{sr_id}", response_model=SRDetailResponse)
async def get_service_request_detail(
    sr_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRDetailResponse:
    detail = await svc.get_sr_detail(sr_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Service request not found")
    return detail


@router.post("/{sr_id}/withdraw", status_code=204)
async def withdraw_service_request(
    sr_id: str,
    request: SRWithdrawRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
):
    try:
        await svc.withdraw_sr(sr_id, request.reason)
    except ICMSRAlreadyWithdrawnError:
        raise HTTPException(status_code=409, detail="Service request already withdrawn")
    except ICMError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return None
