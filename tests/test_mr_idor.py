"""Tests for IDOR fix: monthly report operations must pass profile_id to Siebel client."""
import pytest
from unittest.mock import AsyncMock

from app.domains.monthly_reports.service import MonthlyReportService


@pytest.fixture
def svc():
    from app.domains.account.pin_service import PINService
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)
    return MonthlyReportService(mr_client=AsyncMock(), pin_service=pin_svc)


# ---------------------------------------------------------------------------
# get_answers must pass profile_id to the Siebel client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_answers_passes_profile_id(svc):
    svc._client.get_ia_questionnaire = AsyncMock(return_value={"answers": {}})
    await svc.get_answers(sd81_id="sd81-1", profile_id="user-A")
    svc._client.get_ia_questionnaire.assert_called_once_with(
        "sd81-1", profile_id="user-A"
    )


# ---------------------------------------------------------------------------
# save_answers must pass profile_id to the Siebel client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_answers_passes_profile_id(svc):
    svc._client.finalize = AsyncMock(return_value={"ok": True})
    await svc.save_answers(
        sd81_id="sd81-1", answers={"q1": "yes"}, profile_id="user-A"
    )
    svc._client.finalize.assert_called_once_with(
        "sd81-1", {"q1": "yes"}, profile_id="user-A"
    )


# ---------------------------------------------------------------------------
# submit_report must pass profile_id to the Siebel client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_report_passes_profile_id(svc):
    svc._client.submit_monthly_report = AsyncMock(
        return_value={"status": "SUB", "submitted_at": "2026-03-18T12:00:00+00:00"}
    )
    await svc.submit_report(
        sd81_id="sd81-1",
        pin="1234",
        spouse_pin=None,
        bceid_guid="guid-1",
        profile_id="user-A",
    )
    svc._client.submit_monthly_report.assert_called_once_with(
        "sd81-1", {"pin": "1234", "spouse_pin": None}, profile_id="user-A"
    )


# ---------------------------------------------------------------------------
# restart_report must pass profile_id to the Siebel client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_report_passes_profile_id(svc):
    svc._client.restart_report = AsyncMock(return_value={"status": "RST"})
    await svc.restart_report(sd81_id="sd81-1", profile_id="user-A")
    svc._client.restart_report.assert_called_once_with(
        "sd81-1", profile_id="user-A"
    )


# ---------------------------------------------------------------------------
# get_report_pdf must pass profile_id to the Siebel client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_pdf_passes_profile_id(svc):
    svc._client.get_report_pdf = AsyncMock(return_value=b"%PDF-1.4 mock")
    await svc.get_report_pdf(sd81_id="sd81-1", profile_id="user-A")
    svc._client.get_report_pdf.assert_called_once_with(
        "sd81-1", profile_id="user-A"
    )


# ---------------------------------------------------------------------------
# Backward compatibility: profile_id defaults to None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_answers_works_without_profile_id(svc):
    """Backward compat: callers that omit profile_id should still work."""
    svc._client.get_ia_questionnaire = AsyncMock(return_value={"answers": {}})
    await svc.get_answers(sd81_id="sd81-1")
    svc._client.get_ia_questionnaire.assert_called_once_with(
        "sd81-1", profile_id=None
    )
