import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.services.icm.deps import get_siebel_payment_client
from app.services.feature_flags import FeatureFlagService
from app.domains.payment.models import (
    ChequeScheduleResponse,
    MISPaymentData,
    PaymentInfoResponse,
    T5SlipList,
)
from app.domains.payment.service import PaymentService

payment_router = APIRouter(prefix="/payment", tags=["payment"])


def _get_payment_service() -> PaymentService:
    return PaymentService(client=get_siebel_payment_client())


@payment_router.get("/info", response_model=PaymentInfoResponse)
async def get_payment_info(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PaymentService = Depends(_get_payment_service),
) -> PaymentInfoResponse:
    return await svc.get_payment_info(user.user_id)


@payment_router.get("/schedule", response_model=ChequeScheduleResponse)
async def get_cheque_schedule(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PaymentService = Depends(_get_payment_service),
) -> ChequeScheduleResponse:
    return await svc.get_cheque_schedule(user.user_id)


@payment_router.get("/mis-data", response_model=MISPaymentData)
async def get_mis_data(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PaymentService = Depends(_get_payment_service),
) -> MISPaymentData:
    return await svc.get_mis_data(user.user_id)


@payment_router.get("/t5-slips", response_model=T5SlipList)
async def get_t5_slips(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PaymentService = Depends(_get_payment_service),
) -> T5SlipList:
    if FeatureFlagService.t5_disabled():
        raise HTTPException(status_code=404, detail="T5 slips feature is not available.")
    return await svc.get_t5_slips(user.user_id)


@payment_router.get("/t5-slips/{year}")
async def get_t5_pdf(
    year: Annotated[int, Path(ge=2000, le=2100)],
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: PaymentService = Depends(_get_payment_service),
) -> StreamingResponse:
    if FeatureFlagService.t5_disabled():
        raise HTTPException(status_code=404, detail="T5 slips feature is not available.")
    try:
        content = await svc.get_t5_pdf(user.user_id, year)
    except ValueError:
        raise HTTPException(status_code=404, detail="T5007 PDF not available for this year.")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="T5007_{year}.pdf"'},
    )
