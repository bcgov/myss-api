from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.domains.account.pin_service import PINService
from app.services.icm.deps import get_siebel_monthly_report_client, get_siebel_account_client
from app.domains.monthly_reports.models import (
    ChequeScheduleWindow,
    SD81ListResponse,
    SD81SubmitRequest,
    SD81SubmitResponse,
)
from app.domains.monthly_reports.service import MonthlyReportService
from app.cache.redis_client import get_redis
import redis.asyncio as aioredis

router = APIRouter(prefix="/monthly-reports", tags=["monthly-reports"])


def _get_mr_service(redis: aioredis.Redis = Depends(get_redis)) -> MonthlyReportService:
    pin_svc = PINService(client=get_siebel_account_client())
    return MonthlyReportService(mr_client=get_siebel_monthly_report_client(), pin_service=pin_svc, redis=redis)


@router.get("/current-period", response_model=ChequeScheduleWindow)
async def get_current_period(
    case_number: str = Query("default"),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> ChequeScheduleWindow:
    """Return the current cheque schedule window. Redis caching is a future concern."""
    return await svc.get_current_period(case_number)


@router.get("", response_model=SD81ListResponse)
async def list_reports(
    days_ago: int = Query(365, ge=1),
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> SD81ListResponse:
    return await svc.list_reports(profile_id=user.user_id, days_ago=days_ago)


@router.post("", status_code=201)
async def start_report(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> dict:
    return await svc.start_report(profile_id=user.user_id)


@router.get("/{sd81_id}/answers")
async def get_answers(
    sd81_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> dict:
    return await svc.get_answers(sd81_id=sd81_id, profile_id=user.user_id)


@router.put("/{sd81_id}/answers")
async def save_answers(
    sd81_id: str,
    answers: dict,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> dict:
    return await svc.save_answers(sd81_id=sd81_id, answers=answers, profile_id=user.user_id)


@router.post("/{sd81_id}/submit", response_model=SD81SubmitResponse)
async def submit_report(
    sd81_id: str,
    request: SD81SubmitRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> SD81SubmitResponse:
    # ReportingPeriodClosedError → 422, PINValidationError → 403, and
    # ICMServiceUnavailableError → 503 are handled by global exception
    # handlers in app/exception_handlers.py
    return await svc.submit_report(
        sd81_id=sd81_id,
        pin=request.pin,
        spouse_pin=request.spouse_pin,
        bceid_guid=user.bceid_guid or user.user_id,
        profile_id=user.user_id,
    )


@router.post("/{sd81_id}/restart")
async def restart_report(
    sd81_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> dict:
    return await svc.restart_report(sd81_id=sd81_id, profile_id=user.user_id)


@router.get("/{sd81_id}/pdf")
async def get_report_pdf(
    sd81_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: MonthlyReportService = Depends(_get_mr_service),
) -> StreamingResponse:
    pdf_bytes = await svc.get_report_pdf(sd81_id=sd81_id, profile_id=user.user_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={sd81_id}.pdf"},
    )
