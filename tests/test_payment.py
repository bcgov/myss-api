"""Tests for Payment API endpoints (Task 29)."""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domains.payment.models import (
    AllowanceItem,
    BenefitCode,
    ChequeScheduleResponse,
    DeductionItem,
    MISPaymentData,
    PaymentInfoResponse,
    ServiceProviderPayment,
    SupplementItem,
    T5Slip,
    T5SlipList,
)
from app.domains.payment.service import PaymentService
from app.routers.payment import _get_payment_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_token(role: str = "CLIENT", secret: str = "change-me-in-production") -> str:
    payload = {"sub": "user1", "role": role}
    return pyjwt.encode(payload, secret, algorithm="HS256")


_NOW = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
_TODAY = date(2026, 3, 18)
_FUTURE_DATE = date(2026, 4, 1)

_STUB_MIS_DATA = MISPaymentData(
    mis_person_id="MIS-001",
    key_player_name="Jane Doe",
    spouse_name=None,
    payment_method="Direct Deposit",
    payment_distribution="Full",
    allowances=[
        AllowanceItem(
            code=BenefitCode.SUPPORT,
            amount=Decimal("935.00"),
            description="Support allowance",
        )
    ],
    deductions=[
        DeductionItem(
            code="DED-01",
            amount=Decimal("50.00"),
            description="Overpayment deduction",
        )
    ],
    aee_balance=None,
)

_STUB_PAYMENT_INFO = PaymentInfoResponse(
    upcoming_benefit_date=_FUTURE_DATE,
    assistance_type="Income Assistance",
    supplements=[
        SupplementItem(
            code="SUPP-01",
            amount=Decimal("100.00"),
            effective_date=_TODAY,
        )
    ],
    service_provider_payments=[
        ServiceProviderPayment(
            provider_name="BC Housing",
            amount=Decimal("500.00"),
            payment_date=_FUTURE_DATE,
        )
    ],
    mis_data=_STUB_MIS_DATA,
)

_STUB_CHEQUE_SCHEDULE = ChequeScheduleResponse(
    benefit_month=date(2026, 4, 1),
    income_date=date(2026, 3, 25),
    cheque_issue_date=date(2026, 3, 28),
    period_close_date=datetime(2026, 3, 21, 16, 0, 0, tzinfo=timezone.utc),
)

_STUB_T5_SLIP_LIST = T5SlipList(
    slips=[
        T5Slip(
            tax_year=2025,
            box_10_amount=Decimal("11220.00"),
            box_11_amount=Decimal("0.00"),
            available=True,
        )
    ]
)

_STUB_PDF_BYTES = b"%PDF-1.4 stub pdf content"


def _make_stub_service() -> PaymentService:
    svc = MagicMock(spec=PaymentService)
    svc.get_payment_info = AsyncMock(return_value=_STUB_PAYMENT_INFO)
    svc.get_cheque_schedule = AsyncMock(return_value=_STUB_CHEQUE_SCHEDULE)
    svc.get_mis_data = AsyncMock(return_value=_STUB_MIS_DATA)
    svc.get_t5_slips = AsyncMock(return_value=_STUB_T5_SLIP_LIST)
    svc.get_t5_pdf = AsyncMock(return_value=_STUB_PDF_BYTES)
    return svc


@pytest.fixture(autouse=True)
def override_payment_service():
    stub_svc = _make_stub_service()
    app.dependency_overrides[_get_payment_service] = lambda: stub_svc
    yield stub_svc
    app.dependency_overrides.pop(_get_payment_service, None)


@pytest.fixture
async def ac() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /payment/info
# ---------------------------------------------------------------------------


async def test_get_payment_info_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "upcoming_benefit_date" in data
    assert "assistance_type" in data
    assert data["assistance_type"] == "Income Assistance"
    assert "supplements" in data
    assert "mis_data" in data


async def test_get_payment_info_returns_401_without_auth(ac):
    response = await ac.get("/payment/info")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /payment/schedule
# ---------------------------------------------------------------------------


async def test_get_cheque_schedule_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "benefit_month" in data
    assert "income_date" in data
    assert "cheque_issue_date" in data
    assert "period_close_date" in data


async def test_get_cheque_schedule_returns_401_without_auth(ac):
    response = await ac.get("/payment/schedule")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /payment/mis-data
# ---------------------------------------------------------------------------


async def test_get_mis_data_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/mis-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "mis_person_id" in data
    assert data["mis_person_id"] == "MIS-001"
    assert "key_player_name" in data
    assert "allowances" in data
    assert "deductions" in data


async def test_get_mis_data_returns_401_without_auth(ac):
    response = await ac.get("/payment/mis-data")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /payment/t5-slips
# ---------------------------------------------------------------------------


async def test_get_t5_slips_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/t5-slips",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "slips" in data
    assert len(data["slips"]) == 1
    assert data["slips"][0]["tax_year"] == 2025


async def test_get_t5_slips_returns_404_when_disabled(ac, monkeypatch):
    monkeypatch.setenv("FEATURE_T5_DISABLED", "true")
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/t5-slips",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_get_t5_slips_returns_401_without_auth(ac):
    response = await ac.get("/payment/t5-slips")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /payment/t5-slips/{year}
# ---------------------------------------------------------------------------


async def test_get_t5_pdf_returns_200_with_streaming_response(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/t5-slips/2025",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "content-disposition" in response.headers
    assert "T5007_2025.pdf" in response.headers["content-disposition"]
    assert response.content == _STUB_PDF_BYTES


async def test_get_t5_pdf_returns_404_when_disabled(ac, monkeypatch):
    monkeypatch.setenv("FEATURE_T5_DISABLED", "true")
    token = make_token("CLIENT")
    response = await ac.get(
        "/payment/t5-slips/2025",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_get_t5_pdf_returns_401_without_auth(ac):
    response = await ac.get("/payment/t5-slips/2025")
    assert response.status_code == 401
