from app.services.icm.client import ICMClient


class SiebelMonthlyReportClient(ICMClient):
    """Siebel REST client for SD81 monthly report operations. Covers: D3."""

    async def get_report_period(self, case_number: str) -> dict:
        return await self._get(f"/cases/{case_number}/report-period")

    async def submit_monthly_report(self, sd81_id: str, submission_data: dict, *, profile_id: str | None = None) -> dict:
        params = {"profile_id": profile_id} if profile_id else {}
        return await self._post(f"/monthly-reports/{sd81_id}/submit", json=submission_data, params=params)

    async def get_ia_questionnaire(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        params = {"profile_id": profile_id} if profile_id else {}
        return await self._get(f"/monthly-reports/{sd81_id}/questionnaire", params=params)

    async def list_reports(self, profile_id: str, days_ago: int) -> dict:
        return await self._get(
            f"/profiles/{profile_id}/monthly-reports",
            params={"days_ago": days_ago},
        )

    async def start_report(self, profile_id: str) -> dict:
        return await self._post(f"/profiles/{profile_id}/monthly-reports")

    async def finalize(self, sd81_id: str, answers: dict, *, profile_id: str | None = None) -> dict:
        params = {"profile_id": profile_id} if profile_id else {}
        return await self._post(f"/monthly-reports/{sd81_id}/finalize", json=answers, params=params)

    async def restart_report(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        params = {"profile_id": profile_id} if profile_id else {}
        return await self._post(f"/monthly-reports/{sd81_id}/restart", params=params)

    async def get_summary(self, sd81_id: str) -> dict:
        return await self._get(f"/monthly-reports/{sd81_id}/summary")

    async def get_report_pdf(self, sd81_id: str, *, profile_id: str | None = None) -> bytes:
        """Fetch the PDF for a finalized monthly report. Returns raw bytes."""
        params = {"profile_id": profile_id} if profile_id else {}
        return await self._get_bytes(f"/monthly-reports/{sd81_id}/pdf", params=params)
