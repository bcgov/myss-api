import structlog
from app.services.icm.monthly_report import SiebelMonthlyReportClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockMonthlyReportClient(SiebelMonthlyReportClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_report_period(self, case_number: str) -> dict:
        return data._report_period(case_number)

    async def submit_monthly_report(self, sd81_id: str, submission_data: dict, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id, "new_status": "SUB", "submitted_at": data._now().isoformat()}

    async def get_ia_questionnaire(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return data.QUESTIONNAIRE

    async def list_reports(self, profile_id: str, days_ago: int) -> dict:
        return data.MONTHLY_REPORTS.get(profile_id, {"reports": [], "total": 0})

    async def start_report(self, profile_id: str) -> dict:
        new_id = f"SD81-NEW-{data.uuid4().hex[:6]}"
        return {"sd81_id": new_id, "benefit_month": data._today().replace(day=1).isoformat(), "status": "PRT"}

    async def finalize(self, sd81_id: str, answers: dict, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id}

    async def restart_report(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id, "new_status": "RST"}

    async def get_summary(self, sd81_id: str) -> dict:
        return data.REPORT_SUMMARY.get(sd81_id, {"sd81_id": sd81_id, "benefit_month": data._today().replace(day=1).isoformat(), "status": "PRT", "answers": {}})

    async def get_report_pdf(self, sd81_id: str, *, profile_id: str | None = None) -> bytes:
        return data.MOCK_PDF_BYTES
