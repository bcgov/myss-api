import pytest
from unittest.mock import AsyncMock
from fakeredis.aioredis import FakeRedis

from app.domains.monthly_reports.service import MonthlyReportService


@pytest.mark.asyncio
async def test_get_current_period_caches_in_redis():
    """Second call to get_current_period should hit Redis cache, not Siebel."""
    redis = FakeRedis(decode_responses=True)
    client = AsyncMock()
    client.get_report_period = AsyncMock(return_value={
        "benefit_month": "2026-03-01",
        "income_date": "2026-03-10",
        "cheque_issue_date": "2026-03-20",
        "period_close_date": "2099-12-31T23:59:59Z",
    })

    svc = MonthlyReportService(mr_client=client, redis=redis)

    # First call hits Siebel
    await svc.get_current_period("CASE-001")
    assert client.get_report_period.call_count == 1

    # Second call should hit cache — Siebel call count stays at 1
    await svc.get_current_period("CASE-001")
    assert client.get_report_period.call_count == 1


@pytest.mark.asyncio
async def test_get_current_period_works_without_redis():
    """Service works fine when Redis is not provided (no caching)."""
    client = AsyncMock()
    client.get_report_period = AsyncMock(return_value={
        "benefit_month": "2026-03-01",
        "income_date": "2026-03-10",
        "cheque_issue_date": "2026-03-20",
        "period_close_date": "2099-12-31T23:59:59Z",
    })

    svc = MonthlyReportService(mr_client=client, redis=None)

    await svc.get_current_period("CASE-001")
    await svc.get_current_period("CASE-001")
    # Both calls hit Siebel since no cache
    assert client.get_report_period.call_count == 2
