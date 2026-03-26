import structlog
from app.services.icm.payment import SiebelPaymentClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockPaymentClient(SiebelPaymentClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_payment_info(self, case_number: str) -> dict:
        resolved = data.resolve_case_number(case_number)
        info = dict(data.PAYMENT_INFO.get(resolved, data.PAYMENT_INFO[data.ALICE_CASE]))
        info["upcoming_benefit_date"] = (data._today().replace(day=20)).isoformat()
        return info

    async def get_cheque_schedule(self, case_number: str) -> dict:
        return data._cheque_schedule(case_number)

    async def get_t5007_slips(self, profile_id: str) -> dict:
        resolved = data.resolve_profile_id(profile_id)
        return data.T5007_SLIPS.get(resolved, {"slips": []})

    async def get_t5_history_years(self, profile_id: str) -> dict:
        resolved = data.resolve_profile_id(profile_id)
        return data.T5_HISTORY_YEARS.get(resolved, {"years": []})

    async def get_mis_data(self, profile_id: str) -> dict:
        resolved = data.resolve_profile_id(profile_id)
        return data.MIS_DATA.get(resolved, data.MIS_DATA[data.ALICE_PROFILE_ID])

    async def get_t5007_pdf(self, profile_id: str, year: int) -> dict:
        return {"pdf_data": data.MOCK_PDF_BASE64, "filename": f"T5007_{year}.pdf"}
