"""Tests for the database seeder script."""

import pytest
import sys
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from seed_db import (
    seed_users, seed_profiles, seed_sr_drafts, seed_attachments,
    ALICE_USER_ID, ALICE_PROFILE_ID, ALICE_BCEID,
)
from app.models.user import User, Profile
from app.models.service_requests import SRDraft


@pytest.fixture
async def db_session():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]
    async with async_session() as session:
        yield session
    await engine.dispose()


class TestSeedUsers:
    @pytest.mark.asyncio
    async def test_creates_three_users(self, db_session):
        created = await seed_users(db_session)
        await db_session.commit()
        assert created is True
        alice = await db_session.get(User, ALICE_USER_ID)
        assert alice is not None
        assert alice.bceid_guid == ALICE_BCEID

    @pytest.mark.asyncio
    async def test_idempotent(self, db_session):
        await seed_users(db_session)
        await db_session.commit()
        created = await seed_users(db_session)
        assert created is False


class TestSeedProfiles:
    @pytest.mark.asyncio
    async def test_creates_profiles_linked_to_users(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await db_session.commit()
        profile = await db_session.get(Profile, ALICE_PROFILE_ID)
        assert profile is not None
        assert profile.user_id == ALICE_USER_ID
        assert profile.link_code == "LINKED"


class TestSeedSRDrafts:
    @pytest.mark.asyncio
    async def test_sr_draft_user_id_is_string(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await seed_sr_drafts(db_session)
        await db_session.commit()
        draft = await db_session.get(SRDraft, "seed-sr-alice-assist")
        assert draft is not None
        assert draft.user_id == str(ALICE_USER_ID)
        assert draft.sr_type == "ASSIST"


class TestSeedAttachments:
    @pytest.mark.asyncio
    async def test_creates_three_attachments_with_scan_jobs(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await seed_sr_drafts(db_session)
        await seed_attachments(db_session)
        await db_session.commit()
        from sqlalchemy import text
        result = await db_session.execute(text("SELECT count(*) FROM attachmentrecord"))
        assert result.scalar() == 3
        result = await db_session.execute(text("SELECT count(*) FROM scanjob"))
        assert result.scalar() == 3
