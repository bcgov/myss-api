import pytest
from unittest.mock import AsyncMock
from app.services.icm.monthly_report import SiebelMonthlyReportClient


@pytest.mark.asyncio
async def test_get_report_pdf_uses_circuit_breaker():
    """get_report_pdf must route through _get_bytes (which uses circuit breaker)."""
    client = SiebelMonthlyReportClient(
        base_url="https://test.example.com",
        client_id="id",
        client_secret="secret",
        token_url="https://test.example.com/token",
        _test_no_wait=True,
    )
    # Mock _get_bytes to avoid real HTTP calls
    client._get_bytes = AsyncMock(return_value=b"%PDF-1.4")
    result = await client.get_report_pdf("sd81-1")
    assert result == b"%PDF-1.4"
    client._get_bytes.assert_called_once()
