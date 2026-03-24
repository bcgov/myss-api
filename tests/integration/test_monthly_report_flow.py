"""Integration test for SD81 monthly report lifecycle.

Uses real MonthlyReportService with mocked SiebelMonthlyReportClient.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import jwt as pyjwt
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.icm.monthly_report import SiebelMonthlyReportClient
from app.domains.account.pin_service import PINService
from app.domains.monthly_reports.service import MonthlyReportService
from app.routers.monthly_reports import _get_mr_service


def make_token(role="CLIENT", secret="change-me-in-production"):
    return pyjwt.encode({"sub": "user1", "role": role}, secret, algorithm="HS256")


_FUTURE_CLOSE = datetime(2026, 4, 30, 16, 0, 0, tzinfo=timezone.utc)
_PAST_CLOSE = datetime(2026, 3, 1, 16, 0, 0, tzinfo=timezone.utc)


def _stub_mr_client(period_close_date: datetime = _FUTURE_CLOSE) -> SiebelMonthlyReportClient:
    """Create a SiebelMonthlyReportClient stub with mocked methods for the full SD81 lifecycle."""
    client = AsyncMock(spec=SiebelMonthlyReportClient)

    client.get_report_period = AsyncMock(return_value={
        "benefit_month": "2026-04-01",
        "income_date": "2026-04-10",
        "cheque_issue_date": "2026-04-20",
        "period_close_date": period_close_date.isoformat(),
    })

    client.list_reports = AsyncMock(return_value={
        "reports": [
            {
                "sd81_id": "SD81-FLOW-001",
                "benefit_month": "2026-04-01",
                "status": "PRT",
                "submitted_at": None,
            }
        ],
        "total": 1,
    })

    client.start_report = AsyncMock(return_value={"sd81_id": "SD81-FLOW-001"})

    client.get_ia_questionnaire = AsyncMock(return_value={"q1": "", "q2": ""})

    client.finalize = AsyncMock(return_value={"q1": "yes", "q2": "no"})

    client.submit_monthly_report = AsyncMock(return_value={
        "status": "SUB",
        "submitted_at": "2026-03-18T12:00:00+00:00",
    })

    client.restart_report = AsyncMock(return_value={
        "sd81_id": "SD81-FLOW-001",
        "status": "RST",
    })

    client.get_report_pdf = AsyncMock(return_value=b"%PDF-1.4 test")

    return client


async def test_full_sd81_lifecycle():
    """Open period flow: get period → start → get answers → save answers → submit.

    Uses real MonthlyReportService with mocked SiebelMonthlyReportClient.
    """
    mock_client = _stub_mr_client(period_close_date=_FUTURE_CLOSE)
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)
    svc = MonthlyReportService(mr_client=mock_client, pin_service=pin_svc)

    app.dependency_overrides[_get_mr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}
            sd81_id = "SD81-FLOW-001"

            # 1. GET /monthly-reports/current-period → 200, has all ChequeScheduleWindow fields
            r = await ac.get("/monthly-reports/current-period", headers=headers)
            assert r.status_code == 200
            data = r.json()
            assert "benefit_month" in data
            assert "income_date" in data
            assert "cheque_issue_date" in data
            assert "period_close_date" in data

            # 2. POST /monthly-reports → 201, returns sd81_id
            r = await ac.post("/monthly-reports", headers=headers)
            assert r.status_code == 201
            assert r.json()["sd81_id"] == sd81_id

            # 3. GET /monthly-reports/{sd81_id}/answers → 200
            r = await ac.get(f"/monthly-reports/{sd81_id}/answers", headers=headers)
            assert r.status_code == 200
            assert r.json() == {"q1": "", "q2": ""}

            # 4. PUT /monthly-reports/{sd81_id}/answers → 200 with saved answers
            r = await ac.put(
                f"/monthly-reports/{sd81_id}/answers",
                json={"q1": "yes", "q2": "no"},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json() == {"q1": "yes", "q2": "no"}

            # 5. POST /monthly-reports/{sd81_id}/submit → 200, status is "SUB"
            r = await ac.post(
                f"/monthly-reports/{sd81_id}/submit",
                json={"pin": "1234"},
                headers=headers,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "SUB"

            # Assert submit_monthly_report was called on the client
            mock_client.submit_monthly_report.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(_get_mr_service, None)


async def test_period_closed_submit_returns_422():
    """POST /monthly-reports/{sd81_id}/submit returns 422 when period_close_date is in the past."""
    mock_client = _stub_mr_client(period_close_date=_PAST_CLOSE)
    svc = MonthlyReportService(mr_client=mock_client)

    app.dependency_overrides[_get_mr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.post(
                "/monthly-reports/SD81-FLOW-001/submit",
                json={"pin": "1234"},
                headers=headers,
            )
            assert r.status_code == 422
            assert "closed" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(_get_mr_service, None)


async def test_restart_returns_200():
    """POST /monthly-reports/{sd81_id}/restart returns 200."""
    mock_client = _stub_mr_client()
    svc = MonthlyReportService(mr_client=mock_client)

    app.dependency_overrides[_get_mr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.post("/monthly-reports/SD81-FLOW-001/restart", headers=headers)
            assert r.status_code == 200
            body = r.json()
            assert body["sd81_id"] == "SD81-FLOW-001"
            assert body["status"] == "RST"
    finally:
        app.dependency_overrides.pop(_get_mr_service, None)


async def test_pdf_download():
    """GET /monthly-reports/{sd81_id}/pdf returns 200 with PDF bytes."""
    mock_client = _stub_mr_client()
    svc = MonthlyReportService(mr_client=mock_client)

    app.dependency_overrides[_get_mr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.get("/monthly-reports/SD81-FLOW-001/pdf", headers=headers)
            assert r.status_code == 200
            assert r.content == b"%PDF-1.4 test"
            assert "application/pdf" in r.headers["content-type"]
    finally:
        app.dependency_overrides.pop(_get_mr_service, None)
