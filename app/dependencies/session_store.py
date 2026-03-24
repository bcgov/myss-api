"""Generic Redis-backed session store with TTL and expiry checking."""

from datetime import datetime, timezone
from typing import Generic, Type, TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class RedisSessionStore(Generic[T]):
    """Generic Redis-backed session store with TTL and expiry checking."""

    def __init__(
        self, redis: aioredis.Redis, prefix: str, ttl: int, model_class: Type[T]
    ):
        self._redis = redis
        self._prefix = prefix
        self._ttl = ttl
        self._model_class = model_class

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def set(self, key: str, session: T) -> None:
        await self._redis.setex(self._key(key), self._ttl, session.model_dump_json())

    async def get(self, key: str) -> T | None:
        raw = await self._redis.get(self._key(key))
        if raw is None:
            return None
        session = self._model_class.model_validate_json(raw)
        if hasattr(session, "expires_at"):
            expires_at = session.expires_at
            # Handle string datetime from JSON serialization
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                await self.delete(key)
                return None
        return session

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._key(key))

    async def clear(self) -> None:
        keys: list[bytes | str] = []
        async for key in self._redis.scan_iter(match=f"{self._prefix}*"):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)
