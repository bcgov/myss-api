"""Dependency for AO Registration session validation, backed by Redis."""

from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Header, HTTPException, status, Depends

from app.cache.redis_client import get_redis
from app.dependencies.session_store import RedisSessionStore
from app.models.ao_registration import AORegistrationSession

_PREFIX = "ao_session:"
_TTL = 2592000  # 30 days (matches the session expiry used in AO login)

_store: RedisSessionStore[AORegistrationSession] | None = None


def _get_store(redis_client: aioredis.Redis) -> RedisSessionStore[AORegistrationSession]:
    global _store
    if _store is None or _store._redis is not redis_client:
        _store = RedisSessionStore(
            redis=redis_client,
            prefix=_PREFIX,
            ttl=_TTL,
            model_class=AORegistrationSession,
        )
    return _store


async def set_ao_session(
    key: str, session: AORegistrationSession, redis: aioredis.Redis
) -> None:
    store = _get_store(redis)
    await store.set(key, session)


async def get_ao_session(
    key: str, redis: aioredis.Redis
) -> AORegistrationSession | None:
    store = _get_store(redis)
    return await store.get(key)


async def delete_ao_session(key: str, redis: aioredis.Redis) -> None:
    store = _get_store(redis)
    await store.delete(key)


async def clear_ao_sessions(redis: aioredis.Redis) -> None:
    store = _get_store(redis)
    await store.clear()


async def require_ao_session(
    x_ao_session_token: str = Header(
        ..., description="AO registration session token"
    ),
    redis: aioredis.Redis = Depends(get_redis),
) -> AORegistrationSession:
    """Dependency: look up AO session by X-AO-Session-Token header.

    Returns the session if valid and not expired.
    Raises HTTP 401 if not found or expired.
    """
    # RedisSessionStore.get() handles TTL and expires_at checks — returns None for expired
    session = await get_ao_session(x_ao_session_token, redis)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AO registration session not found or expired",
        )
    return session
