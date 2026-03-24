"""Tests for RedisSessionStore (Task 7)."""

import pytest
from datetime import datetime, timedelta, timezone

from fakeredis.aioredis import FakeRedis
from pydantic import BaseModel

from app.dependencies.session_store import RedisSessionStore


class FakeSession(BaseModel):
    worker_idir: str
    expires_at: datetime


@pytest.fixture
def redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def store(redis):
    return RedisSessionStore(
        redis=redis, prefix="test:", ttl=900, model_class=FakeSession
    )


@pytest.mark.asyncio
async def test_set_and_get(store):
    session = FakeSession(
        worker_idir="JDOE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    await store.set("key1", session)
    result = await store.get("key1")
    assert result is not None
    assert result.worker_idir == "JDOE"


@pytest.mark.asyncio
async def test_get_missing_returns_none(store):
    assert await store.get("nonexistent") is None


@pytest.mark.asyncio
async def test_delete(store):
    session = FakeSession(
        worker_idir="JDOE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    await store.set("key1", session)
    await store.delete("key1")
    assert await store.get("key1") is None


@pytest.mark.asyncio
async def test_expired_session_returns_none(store):
    session = FakeSession(
        worker_idir="JDOE",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await store.set("key1", session)
    assert await store.get("key1") is None


@pytest.mark.asyncio
async def test_clear(store):
    session1 = FakeSession(
        worker_idir="JDOE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    session2 = FakeSession(
        worker_idir="ASMITH",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    await store.set("key1", session1)
    await store.set("key2", session2)
    await store.clear()
    assert await store.get("key1") is None
    assert await store.get("key2") is None
