# app/domains/eligibility/rate_table_service.py
import json
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.domains.eligibility.models import AssetLimitRow, RateRow

INCOME_RATES_CACHE_KEY = "rate_table:eligibility:income"
ASSET_LIMITS_CACHE_KEY = "rate_table:eligibility:assets"
CACHE_TTL_SECONDS = 86_400  # 24 hours (BR-D9-09: rates change at most annually)


class RateTableService:
    """Loads income rates and asset limits from PostgreSQL, caches in Redis."""

    def __init__(self, session: AsyncSession, redis: aioredis.Redis) -> None:
        self._session = session
        self._redis = redis

    async def get_income_rates(self) -> list[RateRow]:
        cached = await self._redis.get(INCOME_RATES_CACHE_KEY)
        if cached:
            raw = json.loads(cached)
            return [RateRow(**r) for r in raw]

        result = await self._session.execute(
            text(
                "SELECT family_size, type_a, type_b, type_c, type_d, type_e "
                "FROM eligibility_rate_table "
                "WHERE effective_from = ("
                "  SELECT MAX(effective_from) FROM eligibility_rate_table"
                ") ORDER BY family_size"
            )
        )
        rows = [
            RateRow(
                family_size=r.family_size,
                type_a=Decimal(str(r.type_a)),
                type_b=Decimal(str(r.type_b)),
                type_c=Decimal(str(r.type_c)),
                type_d=Decimal(str(r.type_d)),
                type_e=Decimal(str(r.type_e)),
            )
            for r in result.fetchall()
        ]
        await self._redis.setex(
            INCOME_RATES_CACHE_KEY,
            CACHE_TTL_SECONDS,
            json.dumps([r.model_dump(mode="json") for r in rows]),
        )
        return rows

    async def get_asset_limits(self) -> list[AssetLimitRow]:
        cached = await self._redis.get(ASSET_LIMITS_CACHE_KEY)
        if cached:
            raw = json.loads(cached)
            return [AssetLimitRow(**r) for r in raw]

        result = await self._session.execute(
            text(
                "SELECT limit_type, limit "
                "FROM eligibility_asset_limit "
                "WHERE effective_from = ("
                "  SELECT MAX(effective_from) FROM eligibility_asset_limit"
                ") ORDER BY limit_type"
            )
        )
        rows = [
            AssetLimitRow(limit_type=r.limit_type, limit=Decimal(str(r.limit)))
            for r in result.fetchall()
        ]
        await self._redis.setex(
            ASSET_LIMITS_CACHE_KEY,
            CACHE_TTL_SECONDS,
            json.dumps([r.model_dump(mode="json") for r in rows]),
        )
        return rows

    async def invalidate_cache(self) -> None:
        """Call after admin rate update to force fresh DB read on next request."""
        await self._redis.delete(INCOME_RATES_CACHE_KEY, ASSET_LIMITS_CACHE_KEY)
