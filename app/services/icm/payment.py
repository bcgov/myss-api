from app.services.icm.client import ICMClient


class SiebelPaymentClient(ICMClient):
    """Siebel REST client for payment information. Covers: D5."""

    async def get_payment_info(self, case_number: str) -> dict:
        return await self._get(f"/cases/{case_number}/payment")

    async def get_cheque_schedule(self, case_number: str) -> dict:
        return await self._get(f"/cases/{case_number}/cheque-schedule")

    async def get_t5007_slips(self, profile_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/t5007-slips")

    async def get_t5_history_years(self, profile_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/t5-history-years")

    async def get_mis_data(self, profile_id: str) -> dict:
        return await self._get(f"/profiles/{profile_id}/mis-data")

    async def get_t5007_pdf(self, profile_id: str, year: int) -> dict:
        return await self._get(f"/profiles/{profile_id}/t5007-slips/{year}/pdf")
