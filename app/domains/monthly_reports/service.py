import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.services.icm.monthly_report import SiebelMonthlyReportClient
from app.domains.account.pin_service import PINService
from app.cache.keys import icm_cheque_schedule_key, ICM_CHEQUE_SCHEDULE_TTL
from app.domains.monthly_reports.models import (
    ChequeScheduleWindow,
    SD81ListResponse,
    SD81Status,
    SD81Summary,
    SD81SubmitResponse,
)


class ReportingPeriodClosedError(Exception):
    """Reporting period has closed and no further submissions are accepted."""


class MonthlyReportService:
    def __init__(
        self,
        mr_client: SiebelMonthlyReportClient,
        pin_service: PINService | None = None,
        redis: aioredis.Redis | None = None,
    ):
        self._client = mr_client
        self._pin_service = pin_service
        self._redis = redis

    async def get_current_period(self, case_number: str) -> ChequeScheduleWindow:
        # Check Redis cache first
        if self._redis:
            key = icm_cheque_schedule_key(case_number)
            cached = await self._redis.get(key)
            if cached:
                return ChequeScheduleWindow.model_validate_json(cached)

        raw = await self._client.get_report_period(case_number)
        result = ChequeScheduleWindow(**raw)

        # Cache the result
        if self._redis:
            await self._redis.setex(key, ICM_CHEQUE_SCHEDULE_TTL, result.model_dump_json())

        return result

    async def list_reports(self, profile_id: str, days_ago: int) -> SD81ListResponse:
        raw = await self._client.list_reports(profile_id, days_ago)
        reports_raw = raw.get("reports", [])
        reports = [SD81Summary(**r) for r in reports_raw]
        total = raw.get("total", len(reports))
        return SD81ListResponse(reports=reports, total=total)

    async def start_report(self, profile_id: str) -> dict:
        result = await self._client.start_report(profile_id)
        return {"sd81_id": result.get("sd81_id", "")}

    async def get_answers(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return await self._client.get_ia_questionnaire(sd81_id, profile_id=profile_id)

    async def save_answers(self, sd81_id: str, answers: dict, *, profile_id: str | None = None) -> dict:
        return await self._client.finalize(sd81_id, answers, profile_id=profile_id)

    async def submit_report(
        self,
        sd81_id: str,
        pin: str,
        spouse_pin: str | None,
        bceid_guid: str,
        *,
        profile_id: str | None = None,
    ) -> SD81SubmitResponse:
        from app.services.icm.exceptions import PINValidationError

        # Period-closed check: reject submissions once the benefit month has closed.
        period = await self.get_current_period(profile_id or bceid_guid)
        close = period.period_close_date
        if close.tzinfo is None:
            close = close.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > close:
            raise ReportingPeriodClosedError(
                "Submission period is closed for this benefit month"
            )

        if not self._pin_service:
            raise RuntimeError("PINService not configured")
        if not await self._pin_service.validate(bceid_guid, pin):
            raise PINValidationError("Invalid PIN")

        if spouse_pin and not await self._pin_service.validate(bceid_guid, spouse_pin):
            raise PINValidationError("Invalid spouse PIN")

        # Key player check: stub — accept all (will be implemented in Phase 8)

        result = await self._client.submit_monthly_report(sd81_id, {"pin": pin, "spouse_pin": spouse_pin}, profile_id=profile_id)
        submitted_at_raw = result.get("submitted_at")
        submitted_at = (
            datetime.fromisoformat(submitted_at_raw)
            if submitted_at_raw
            else datetime.now(timezone.utc)
        )
        status_raw = result.get("status", SD81Status.SUBMITTED.value)
        try:
            status = SD81Status(status_raw)
        except ValueError:
            status = SD81Status.SUBMITTED

        return SD81SubmitResponse(
            sd81_id=sd81_id,
            status=status,
            submitted_at=submitted_at,
        )

    async def restart_report(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return await self._client.restart_report(sd81_id, profile_id=profile_id)

    async def get_report_pdf(self, sd81_id: str, *, profile_id: str | None = None) -> bytes:
        return await self._client.get_report_pdf(sd81_id, profile_id=profile_id)
