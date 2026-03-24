"""Tests for Monthly Report API endpoints (Task 23)."""
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.monthly_reports.models import (
    SD81Status,
    ChequeScheduleWindow,
    SD81ListResponse,
    SD81Summary,
    SD81SubmitResponse,
)
from app.domains.monthly_reports.service import MonthlyReportService
from app.routers.monthly_reports import _get_mr_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

_FUTURE_CLOSE = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
_PAST_CLOSE = datetime(2026, 3, 1, 16, 0, 0, tzinfo=timezone.utc)

_STUB_PERIOD = ChequeScheduleWindow(
    benefit_month=date(2026, 3, 1),
    income_date=date(2026, 3, 10),
    cheque_issue_date=date(2026, 3, 20),
    period_close_date=_FUTURE_CLOSE,
)

_STUB_PAST_PERIOD = ChequeScheduleWindow(
    benefit_month=date(2026, 2, 1),
    income_date=date(2026, 2, 10),
    cheque_issue_date=date(2026, 2, 20),
    period_close_date=_PAST_CLOSE,
)

_STUB_LIST = SD81ListResponse(
    reports=[
        SD81Summary(
            sd81_id="SD81-001",
            benefit_month=date(2026, 3, 1),
            status=SD81Status.PARTIAL,
            submitted_at=None,
        )
    ],
    total=1,
)

_STUB_SUBMIT = SD81SubmitResponse(
    sd81_id="SD81-001",
    status=SD81Status.SUBMITTED,
    submitted_at=_NOW,
)


def _make_stub_service() -> MonthlyReportService:
    svc = MagicMock(spec=MonthlyReportService)
    svc.get_current_period = AsyncMock(return_value=_STUB_PERIOD)
    svc.list_reports = AsyncMock(return_value=_STUB_LIST)
    svc.start_report = AsyncMock(return_value={"sd81_id": "SD81-001"})
    svc.get_answers = AsyncMock(return_value={"q1": "yes"})
    svc.save_answers = AsyncMock(return_value={"q1": "yes", "q2": "no"})
    svc.submit_report = AsyncMock(return_value=_STUB_SUBMIT)
    svc.restart_report = AsyncMock(return_value={"sd81_id": "SD81-001", "status": "RST"})
    svc.get_report_pdf = AsyncMock(return_value=b"%PDF-1.4 mock pdf content")
    return svc


@pytest.fixture(autouse=True)
def override_mr_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_mr_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_mr_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /monthly-reports/current-period
# ---------------------------------------------------------------------------


async def test_get_current_period_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports/current-period",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "benefit_month" in data
    assert "income_date" in data
    assert "cheque_issue_date" in data
    assert "period_close_date" in data


async def test_get_current_period_has_correct_types(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports/current-period",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # period_close_date should be an ISO datetime string
    close_dt = datetime.fromisoformat(data["period_close_date"].replace("Z", "+00:00"))
    assert isinstance(close_dt, datetime)
    # benefit_month is a date string YYYY-MM-DD
    assert data["benefit_month"] == "2026-03-01"


async def test_get_current_period_returns_401_without_auth(ac):
    response = await ac.get("/monthly-reports/current-period")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /monthly-reports
# ---------------------------------------------------------------------------


async def test_list_reports_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert "total" in data
    assert data["total"] == 1


async def test_list_reports_passes_days_ago_query_param(ac, override_mr_service):
    token = make_token("CLIENT")
    await ac.get(
        "/monthly-reports?days_ago=180",
        headers={"Authorization": f"Bearer {token}"},
    )
    override_mr_service.list_reports.assert_awaited_once_with(
        profile_id="user1", days_ago=180
    )


async def test_list_reports_returns_401_without_auth(ac):
    response = await ac.get("/monthly-reports")
    assert response.status_code == 401


async def test_list_reports_status_serializes_to_3char_code(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["reports"][0]["status"] == "PRT"


# ---------------------------------------------------------------------------
# POST /monthly-reports  (start new report)
# ---------------------------------------------------------------------------


async def test_start_report_returns_201(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/monthly-reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "sd81_id" in data
    assert data["sd81_id"] == "SD81-001"


async def test_start_report_returns_401_without_auth(ac):
    response = await ac.post("/monthly-reports")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /monthly-reports/{sd81_id}/answers
# ---------------------------------------------------------------------------


async def test_get_answers_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports/SD81-001/answers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"q1": "yes"}


async def test_get_answers_returns_401_without_auth(ac):
    response = await ac.get("/monthly-reports/SD81-001/answers")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /monthly-reports/{sd81_id}/answers
# ---------------------------------------------------------------------------


async def test_save_answers_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.put(
        "/monthly-reports/SD81-001/answers",
        json={"q1": "yes", "q2": "no"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"q1": "yes", "q2": "no"}


async def test_save_answers_returns_401_without_auth(ac):
    response = await ac.put(
        "/monthly-reports/SD81-001/answers",
        json={"q1": "yes"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /monthly-reports/{sd81_id}/submit
# ---------------------------------------------------------------------------


async def test_submit_report_returns_200_with_future_close_date(ac, override_mr_service):
    # period_close_date is in the future
    override_mr_service.get_current_period = AsyncMock(return_value=_STUB_PERIOD)
    token = make_token("CLIENT")
    response = await ac.post(
        "/monthly-reports/SD81-001/submit",
        json={"pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "sd81_id" in data
    assert "status" in data
    assert "submitted_at" in data


async def test_submit_report_returns_422_when_period_closed(ac, override_mr_service):
    # period_close_date is in the past
    override_mr_service.get_current_period = AsyncMock(return_value=_STUB_PAST_PERIOD)
    token = make_token("CLIENT")
    response = await ac.post(
        "/monthly-reports/SD81-001/submit",
        json={"pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "closed" in response.json()["detail"].lower()


async def test_submit_report_status_is_submitted(ac, override_mr_service):
    override_mr_service.get_current_period = AsyncMock(return_value=_STUB_PERIOD)
    token = make_token("CLIENT")
    response = await ac.post(
        "/monthly-reports/SD81-001/submit",
        json={"pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUB"


async def test_submit_report_returns_401_without_auth(ac):
    response = await ac.post(
        "/monthly-reports/SD81-001/submit",
        json={"pin": "1234"},
    )
    assert response.status_code == 401


async def test_submit_report_calls_service_with_correct_args(ac, override_mr_service):
    override_mr_service.get_current_period = AsyncMock(return_value=_STUB_PERIOD)
    token = make_token("CLIENT")
    await ac.post(
        "/monthly-reports/SD81-001/submit",
        json={"pin": "1234", "spouse_pin": "5678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    override_mr_service.submit_report.assert_awaited_once_with(
        sd81_id="SD81-001",
        pin="1234",
        spouse_pin="5678",
        bceid_guid="user1",
        profile_id="user1",
    )


# ---------------------------------------------------------------------------
# POST /monthly-reports/{sd81_id}/restart
# ---------------------------------------------------------------------------


async def test_restart_report_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/monthly-reports/SD81-001/restart",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RST"


async def test_restart_report_returns_401_without_auth(ac):
    response = await ac.post("/monthly-reports/SD81-001/restart")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /monthly-reports/{sd81_id}/pdf
# ---------------------------------------------------------------------------


async def test_get_pdf_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/monthly-reports/SD81-001/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 mock pdf content"
    assert "application/pdf" in response.headers["content-type"]


async def test_get_pdf_returns_401_without_auth(ac):
    response = await ac.get("/monthly-reports/SD81-001/pdf")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# SD81Status enum serializes to 3-char ICM codes
# ---------------------------------------------------------------------------


def test_sd81_status_values_are_3char_codes():
    assert SD81Status.PARTIAL == "PRT"
    assert SD81Status.SUBMITTED == "SUB"
    assert SD81Status.RESTARTED == "RST"
    assert SD81Status.RESUBMITTED == "RES"
    assert SD81Status.PENDING_DOCUMENTS == "PND"


def test_sd81_submit_response_serializes_status_as_code():
    resp = SD81SubmitResponse(
        sd81_id="SD81-001",
        status=SD81Status.SUBMITTED,
        submitted_at=_NOW,
    )
    data = resp.model_dump()
    assert data["status"] == "SUB"
