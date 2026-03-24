"""Dependency for support-view session validation, backed by Redis."""

from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status

from app.cache.redis_client import get_redis
from app.dependencies.require_worker_role import require_worker_role
from app.dependencies.session_store import RedisSessionStore
from app.auth.models import UserContext
from app.models.admin import SupportViewSessionData

_PREFIX = "support_view_session:"
_TTL = 900  # 15 minutes

_store: RedisSessionStore[SupportViewSessionData] | None = None


def _get_store(redis_client: aioredis.Redis) -> RedisSessionStore[SupportViewSessionData]:
    global _store
    if _store is None or _store._redis is not redis_client:
        _store = RedisSessionStore(
            redis=redis_client,
            prefix=_PREFIX,
            ttl=_TTL,
            model_class=SupportViewSessionData,
        )
    return _store


async def set_session(
    key: str, session: SupportViewSessionData, redis: aioredis.Redis
) -> None:
    store = _get_store(redis)
    await store.set(key, session)


async def get_session(
    key: str, redis: aioredis.Redis
) -> SupportViewSessionData | None:
    store = _get_store(redis)
    return await store.get(key)


async def delete_session(key: str, redis: aioredis.Redis) -> None:
    store = _get_store(redis)
    await store.delete(key)


async def clear_sessions(redis: aioredis.Redis) -> None:
    store = _get_store(redis)
    await store.clear()


async def require_support_view_session(
    x_support_view_client: str = Header(
        ..., description="Client BCeID GUID for support view"
    ),
    user: UserContext = Depends(require_worker_role),
    redis: aioredis.Redis = Depends(get_redis),
) -> SupportViewSessionData:
    key = f"{user.idir_username}:{x_support_view_client}"
    # RedisSessionStore.get() handles TTL and expires_at checks — returns None for expired
    session = await get_session(key, redis)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Support view session not found or expired",
        )
    return session
