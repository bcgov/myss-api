import pytest
import fakeredis.aioredis
from uuid import UUID, uuid4
from app.cache.keys import (
    session_key,
    icm_case_key,
    icm_payment_key,
    icm_cheque_schedule_key,
    icm_banners_key,
    support_view_key,
    pin_reset_key,
    SESSION_TTL,
    ICM_CASE_TTL,
    ICM_PAYMENT_TTL,
    ICM_CHEQUE_SCHEDULE_TTL,
    ICM_BANNERS_TTL,
    SUPPORT_VIEW_TTL,
    PIN_RESET_TTL,
)


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


def test_session_key_format():
    uid = uuid4()
    assert session_key(uid) == f"session:{uid}"


def test_icm_case_key_format():
    assert icm_case_key("C-1234") == "icm_cache:case:C-1234"


def test_icm_payment_key_format():
    assert icm_payment_key("C-1234") == "icm_cache:payment:C-1234"


def test_icm_cheque_schedule_key_format():
    assert icm_cheque_schedule_key("C-1234") == "icm_cache:cheque_schedule:C-1234"


def test_icm_banners_key_format():
    assert icm_banners_key("C-1234") == "icm_cache:banners:C-1234"


def test_support_view_key_format():
    assert support_view_key("idir_user1") == "support_view:idir_user1"


def test_pin_reset_key_format():
    uid = uuid4()
    assert pin_reset_key(uid) == f"pin_reset:{uid}"


def test_ttl_values():
    assert SESSION_TTL == 900         # 15 minutes
    assert ICM_CASE_TTL == 300        # 5 minutes
    assert ICM_PAYMENT_TTL == 3600    # 1 hour
    assert ICM_CHEQUE_SCHEDULE_TTL == 3600  # 1 hour
    assert ICM_BANNERS_TTL == 300     # 5 minutes
    assert SUPPORT_VIEW_TTL == 900    # 15 minutes
    assert PIN_RESET_TTL == 3600      # 1 hour


@pytest.mark.asyncio
async def test_set_get_roundtrip(redis):
    uid = uuid4()
    key = session_key(uid)
    await redis.setex(key, SESSION_TTL, '{"role": "CLIENT"}')
    value = await redis.get(key)
    assert value == '{"role": "CLIENT"}'


@pytest.mark.asyncio
async def test_ttl_applied_correctly(redis):
    uid = uuid4()
    key = session_key(uid)
    await redis.setex(key, SESSION_TTL, "test-value")
    ttl = await redis.ttl(key)
    assert 0 < ttl <= SESSION_TTL


@pytest.mark.asyncio
async def test_expired_key_returns_none(redis):
    key = icm_case_key("EXPIRED-CASE")
    await redis.setex(key, 1, "some-data")
    # Set TTL to 0 to expire immediately
    await redis.expire(key, 0)
    value = await redis.get(key)
    assert value is None
