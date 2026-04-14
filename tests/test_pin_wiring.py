"""Tests for Task 3: real PINService injection replaces the always-True stub."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domains.account.pin_service import PINService
from app.domains.service_requests.service import ServiceRequestService
from app.domains.monthly_reports.service import MonthlyReportService
from app.domains.notifications.service import NotificationMessageService


@pytest.mark.asyncio
async def test_sr_submit_uses_real_pin_service():
    """ServiceRequestService.submit_sr must use injected PINService."""
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    sr_client = AsyncMock()
    sr_client.finalize_sr_form = AsyncMock(return_value={"sr_number": "SR-001"})
    session = AsyncMock()

    svc = ServiceRequestService(sr_client=sr_client, session=session, pin_service=pin_svc)
    svc.get_draft = AsyncMock(return_value=MagicMock(
        draft_json={"answers": {}}, sr_type=MagicMock(value="CHANGE_OF_ADDRESS")
    ))

    await svc.submit_sr("sr-1", pin="1234", spouse_pin=None, bceid_guid="guid", user_id="u1")
    pin_svc.validate.assert_called_once_with("guid", "1234")


@pytest.mark.asyncio
async def test_sr_submit_rejects_invalid_pin():
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=False)

    svc = ServiceRequestService(sr_client=AsyncMock(), session=AsyncMock(), pin_service=pin_svc)

    from app.services.icm.exceptions import PINValidationError
    with pytest.raises(PINValidationError, match="Invalid PIN"):
        await svc.submit_sr("sr-1", pin="0000", spouse_pin=None, bceid_guid="guid", user_id="u1")


@pytest.mark.asyncio
async def test_mr_submit_uses_real_pin_service():
    """MonthlyReportService.submit_report must use injected PINService."""
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    mr_client = AsyncMock()
    mr_client.submit_monthly_report = AsyncMock(return_value={"status": "SUBMITTED", "submitted_at": "2026-01-01T00:00:00Z"})
    mr_client.get_report_period = AsyncMock(return_value={
        "benefit_month": "2026-01-01",
        "income_date": "2026-01-10",
        "cheque_issue_date": "2026-01-20",
        "period_close_date": "2099-12-31T23:59:59+00:00",
    })

    svc = MonthlyReportService(mr_client=mr_client, pin_service=pin_svc)
    await svc.submit_report(sd81_id="sd81-1", pin="1234", spouse_pin=None, bceid_guid="guid")
    pin_svc.validate.assert_called_once_with("guid", "1234")


@pytest.mark.asyncio
async def test_notification_sign_uses_real_pin_service():
    """NotificationMessageService.sign_and_send must use injected PINService."""
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    notif_client = AsyncMock()
    notif_client.sign_and_send = AsyncMock(return_value={})

    svc = NotificationMessageService(client=notif_client, pin_service=pin_svc)
    await svc.sign_and_send(msg_id="msg-1", pin="1234", bceid_guid="guid")
    pin_svc.validate.assert_called_once_with("guid", "1234")
