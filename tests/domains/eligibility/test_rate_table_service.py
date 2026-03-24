# tests/domains/eligibility/test_rate_table_service.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from app.domains.eligibility.rate_table_service import RateTableService
from app.domains.eligibility.models import RateRow, AssetLimitRow


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


async def test_get_income_rates_returns_rows(mock_session, mock_redis):
    """RateTableService.get_income_rates() returns list of RateRow."""
    svc = RateTableService(session=mock_session, redis=mock_redis)
    # Stub DB result
    mock_row = MagicMock()
    mock_row.family_size = 1
    mock_row.type_a = Decimal("1060.00")
    mock_row.type_b = Decimal("0")
    mock_row.type_c = Decimal("1535.50")
    mock_row.type_d = Decimal("0")
    mock_row.type_e = Decimal("0")
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[mock_row])))
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    rows = await svc.get_income_rates()
    assert len(rows) >= 1
    assert isinstance(rows[0], RateRow)


async def test_get_asset_limits_returns_rows(mock_session, mock_redis):
    """RateTableService.get_asset_limits() returns list of AssetLimitRow."""
    svc = RateTableService(session=mock_session, redis=mock_redis)
    mock_row = MagicMock()
    mock_row.limit_type = "A"
    mock_row.limit = Decimal("5000.00")
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[mock_row])))
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    rows = await svc.get_asset_limits()
    assert len(rows) >= 1
    assert isinstance(rows[0], AssetLimitRow)
