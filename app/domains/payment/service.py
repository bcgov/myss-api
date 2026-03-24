from app.services.icm.payment import SiebelPaymentClient
from app.domains.payment.models import (
    ChequeScheduleResponse,
    MISPaymentData,
    PaymentInfoResponse,
    T5SlipList,
)


class PaymentService:
    def __init__(self, client: SiebelPaymentClient):
        self._client = client

    async def get_payment_info(self, profile_id: str) -> PaymentInfoResponse:
        data = await self._client.get_payment_info(profile_id)
        return PaymentInfoResponse(**data)

    async def get_cheque_schedule(self, user_id: str) -> ChequeScheduleResponse:
        data = await self._client.get_cheque_schedule(user_id)
        return ChequeScheduleResponse(**data)

    async def get_mis_data(self, profile_id: str) -> MISPaymentData:
        data = await self._client.get_mis_data(profile_id)
        return MISPaymentData(**data)

    async def get_t5_slips(self, profile_id: str) -> T5SlipList:
        data = await self._client.get_t5007_slips(profile_id)
        return T5SlipList(**data)

    async def get_t5_pdf(self, profile_id: str, year: int) -> bytes:
        data = await self._client.get_t5007_pdf(profile_id, year)
        content = data.get("content")
        if not content:
            raise ValueError(f"T5007 PDF content missing for year {year}")
        return content
