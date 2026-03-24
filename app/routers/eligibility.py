# app/routers/eligibility.py
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.db.session import get_session
from app.cache.redis_client import get_redis
from app.domains.eligibility.models import EligibilityRequest, EligibilityResponse, RateRow, AssetLimitRow
from app.domains.eligibility.calculator import EligibilityCalculatorService
from app.domains.eligibility.rate_table_service import RateTableService

router = APIRouter(prefix="/eligibility-estimator", tags=["public"])


def _fallback_income_rates() -> list[RateRow]:
    """FDD BR-D9-05 rates as a fallback if DB is unavailable during startup."""
    return [
        RateRow(family_size=1,  type_a=Decimal("1060.00"),  type_b=Decimal("0"),       type_c=Decimal("1535.50"), type_d=Decimal("0"),       type_e=Decimal("0")),
        RateRow(family_size=2,  type_a=Decimal("1650.00"),  type_b=Decimal("1405.00"), type_c=Decimal("2125.50"), type_d=Decimal("1880.50"), type_e=Decimal("2652.50")),
        RateRow(family_size=3,  type_a=Decimal("1845.00"),  type_b=Decimal("1500.00"), type_c=Decimal("2320.50"), type_d=Decimal("1975.50"), type_e=Decimal("2847.50")),
        RateRow(family_size=4,  type_a=Decimal("1895.00"),  type_b=Decimal("1550.00"), type_c=Decimal("2370.50"), type_d=Decimal("2025.50"), type_e=Decimal("2897.50")),
        RateRow(family_size=5,  type_a=Decimal("1945.00"),  type_b=Decimal("1600.00"), type_c=Decimal("2420.50"), type_d=Decimal("2075.50"), type_e=Decimal("2947.50")),
        RateRow(family_size=6,  type_a=Decimal("1995.00"),  type_b=Decimal("1650.00"), type_c=Decimal("2470.50"), type_d=Decimal("2125.50"), type_e=Decimal("2997.50")),
        RateRow(family_size=7,  type_a=Decimal("2045.00"),  type_b=Decimal("1700.00"), type_c=Decimal("2520.50"), type_d=Decimal("2175.50"), type_e=Decimal("3047.50")),
    ]


def _fallback_asset_limits() -> list[AssetLimitRow]:
    """FDD BR-D9-06 asset limits as a fallback if DB is unavailable during startup."""
    return [
        AssetLimitRow(limit_type="A", limit=Decimal("5000.00")),
        AssetLimitRow(limit_type="B", limit=Decimal("10000.00")),
        AssetLimitRow(limit_type="C", limit=Decimal("100000.00")),
        AssetLimitRow(limit_type="D", limit=Decimal("200000.00")),
    ]


@router.post("/calculate", response_model=EligibilityResponse)
async def calculate_eligibility(
    request: EligibilityRequest,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> EligibilityResponse:
    """Calculate income assistance eligibility estimate.

    This endpoint is entirely anonymous — no authentication is required.
    No data is persisted. Implements BR-D9-01 through BR-D9-09.
    """
    rate_svc = RateTableService(session=session, redis=redis)
    try:
        income_rates = await rate_svc.get_income_rates()
        asset_limits = await rate_svc.get_asset_limits()
    except Exception:
        # Fallback to hard-coded FDD rates if DB unavailable
        # This ensures the estimator remains functional during DB maintenance
        income_rates = _fallback_income_rates()
        asset_limits = _fallback_asset_limits()

    calc = EligibilityCalculatorService(income_rates=income_rates, asset_limits=asset_limits)
    return calc.calculate(request)
