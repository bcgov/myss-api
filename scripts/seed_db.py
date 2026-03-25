#!/usr/bin/env python3
"""
Seed the local database with test data for development.

Usage:
    python scripts/seed_db.py          # idempotent insert
    python scripts/seed_db.py --reset  # truncate and re-insert

Requires DATABASE_URL and JWT_SECRET in environment (or .env file).
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta, UTC
from uuid import UUID

# Ensure the project root is on sys.path so app.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt as pyjwt
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, Profile
from app.models.registration import RegistrationSession
from app.models.ao_registration import AORegistrationSession
from app.models.auth_tokens import PINResetToken
from app.models.service_requests import SRDraft
from app.models.attachments import AttachmentRecord, ScanJob
from app.models.employment import PlanSignatureSession
from app.models.misc import DisclaimerAcknowledgement
from app.models.audit import WorkerAuditRecord

# ---------------------------------------------------------------------------
# Persona constants (must match app/services/icm/mock/data.py)
# ---------------------------------------------------------------------------

ALICE_USER_ID = UUID("a0000000-0000-0000-0000-000000000001")
BOB_USER_ID = UUID("b0000000-0000-0000-0000-000000000002")
CAROL_USER_ID = UUID("c0000000-0000-0000-0000-000000000003")

ALICE_BCEID = "alice-bceid-1001"
BOB_BCEID = "bob-bceid-1002"
CAROL_BCEID = "carol-bceid-1003"

ALICE_PROFILE_ID = UUID("a1000000-0000-0000-0000-000000000001")
BOB_PROFILE_ID = UUID("b1000000-0000-0000-0000-000000000002")
CAROL_PROFILE_ID = UUID("c1000000-0000-0000-0000-000000000003")

WORKER_IDIR = "jsmith"

now = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _get_db_url() -> str:
    """Read DATABASE_URL the same way the app does."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "change-me-in-production")


def _make_jwt(sub: str, role: str, *, bceid_guid: str | None = None, idir_username: str | None = None) -> str:
    payload: dict = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=24),
    }
    if bceid_guid:
        payload["bceid_guid"] = bceid_guid
    if idir_username:
        payload["idir_username"] = idir_username
    return pyjwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_users(session: AsyncSession) -> bool:
    """Create 3 test users. Returns True if created, False if already exist."""
    existing = await session.get(User, ALICE_USER_ID)
    if existing:
        print("  Users already exist, skipping.")
        return False

    users = [
        User(id=ALICE_USER_ID, bceid_guid=ALICE_BCEID, created_at=now, updated_at=now),
        User(id=BOB_USER_ID, bceid_guid=BOB_BCEID, created_at=now, updated_at=now),
        User(id=CAROL_USER_ID, bceid_guid=CAROL_BCEID, created_at=now, updated_at=now),
    ]
    session.add_all(users)
    print("  Created 3 users: Alice, Bob, Carol")
    return True


async def seed_profiles(session: AsyncSession) -> None:
    existing = await session.get(Profile, ALICE_PROFILE_ID)
    if existing:
        print("  Profiles already exist, skipping.")
        return

    profiles = [
        Profile(
            id=ALICE_PROFILE_ID, user_id=ALICE_USER_ID,
            portal_id="PTL-ALICE-001", link_code="LINKED",
            mis_person_id="MIS-001", created_at=now, updated_at=now,
        ),
        Profile(
            id=BOB_PROFILE_ID, user_id=BOB_USER_ID,
            portal_id="PTL-BOB-002", link_code="LINKED",
            mis_person_id="MIS-002", created_at=now, updated_at=now,
        ),
        Profile(
            id=CAROL_PROFILE_ID, user_id=CAROL_USER_ID,
            portal_id="PTL-CAROL-003", link_code="UNLINKED",
            mis_person_id="MIS-003", created_at=now, updated_at=now,
        ),
    ]
    session.add_all(profiles)
    print("  Created 3 profiles: Alice=LINKED, Bob=LINKED, Carol=UNLINKED")


async def seed_registration_sessions(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM registrationsession WHERE invite_token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  Registration sessions already exist, skipping.")
        return

    sessions = [
        RegistrationSession(
            user_id=ALICE_USER_ID,
            invite_token="seed-invite-alice-completed",
            step=6,
            form_state_json={"account_creation_type": "SELF", "completed": True},
            expires_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=2),
        ),
        RegistrationSession(
            invite_token="seed-invite-in-progress",
            step=3,
            form_state_json={"account_creation_type": "SELF", "first_name": "New", "last_name": "Applicant"},
            expires_at=now + timedelta(hours=24),
        ),
    ]
    session.add_all(sessions)
    print("  Created 2 registration sessions: 1 completed, 1 in-progress")


async def seed_pin_reset_tokens(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM pinresettoken WHERE token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  PIN reset tokens already exist, skipping.")
        return

    tokens = [
        PINResetToken(
            profile_id=ALICE_PROFILE_ID,
            token="seed-pin-reset-active",
            expires_at=now + timedelta(hours=1),
        ),
        PINResetToken(
            profile_id=BOB_PROFILE_ID,
            token="seed-pin-reset-expired",
            expires_at=now - timedelta(hours=24),
            used_at=now - timedelta(hours=25),
        ),
    ]
    session.add_all(tokens)
    print("  Created 2 PIN reset tokens: 1 active, 1 expired")


async def seed_ao_registration(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM aoregistrationsession WHERE worker_idir = :idir"),
        {"idir": WORKER_IDIR},
    )
    if result.scalar() > 0:
        print("  AO registration session already exists, skipping.")
        return

    test_sin = "000000000"
    sin_hash = bcrypt.hashpw(test_sin.encode(), bcrypt.gensalt()).decode()

    ao_session = AORegistrationSession(
        worker_idir=WORKER_IDIR,
        applicant_sr_num="SR-AO-001",
        applicant_sin_hash=sin_hash,
        step_reached=1,
        expires_at=now + timedelta(hours=4),
    )
    session.add(ao_session)
    print("  Created 1 AO registration session (test SIN: 000-000-000)")


async def seed_sr_drafts(session: AsyncSession) -> None:
    existing = await session.get(SRDraft, "seed-sr-alice-assist")
    if existing:
        print("  SR drafts already exist, skipping.")
        return

    drafts = [
        SRDraft(
            sr_id="seed-sr-alice-assist",
            user_id=str(ALICE_USER_ID),
            sr_type="ASSIST",
            draft_json={"employment_status": "unemployed", "seeking_employment": True},
            updated_at=now,
        ),
        SRDraft(
            sr_id="seed-sr-alice-crisis",
            user_id=str(ALICE_USER_ID),
            sr_type="CRISIS_FOOD",
            draft_json={},
            updated_at=now,
        ),
        SRDraft(
            sr_id="seed-sr-bob-dd",
            user_id=str(BOB_USER_ID),
            sr_type="DIRECT_DEPOSIT",
            draft_json={"bank_name": "TD Canada Trust", "transit_number": "00123"},
            updated_at=now,
        ),
    ]
    session.add_all(drafts)
    print("  Created 3 SR drafts: ASSIST, CRISIS_FOOD (Alice), DIRECT_DEPOSIT (Bob)")


async def seed_attachments(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM attachmentrecord WHERE storage_path LIKE 'seed/%'")
    )
    if result.scalar() > 0:
        print("  Attachments already exist, skipping.")
        return

    att_alice = AttachmentRecord(
        profile_id=ALICE_PROFILE_ID,
        sr_draft_id="seed-sr-alice-assist",
        filename="proof_of_income.pdf",
        mime_type="application/pdf",
        size_bytes=45000,
        storage_path="seed/alice/proof_of_income.pdf",
        av_status="CLEAN",
        uploaded_at=now,
    )
    att_bob = AttachmentRecord(
        profile_id=BOB_PROFILE_ID,
        sr_draft_id="seed-sr-bob-dd",
        filename="bank_statement.pdf",
        mime_type="application/pdf",
        size_bytes=128000,
        storage_path="seed/bob/bank_statement.pdf",
        av_status="PENDING",
        uploaded_at=now,
    )
    att_carol = AttachmentRecord(
        profile_id=CAROL_PROFILE_ID,
        filename="suspicious_file.exe",
        mime_type="application/octet-stream",
        size_bytes=666,
        storage_path="seed/carol/suspicious_file.exe",
        av_status="INFECTED",
        uploaded_at=now,
    )
    session.add_all([att_alice, att_bob, att_carol])
    await session.flush()  # get IDs

    scans = [
        ScanJob(attachment_id=att_alice.id, status="CLEAN", scanned_at=now),
        ScanJob(attachment_id=att_bob.id, status="QUEUED"),
        ScanJob(attachment_id=att_carol.id, status="INFECTED", scanned_at=now),
    ]
    session.add_all(scans)
    print("  Created 3 attachments + scan jobs: CLEAN, PENDING, INFECTED")


async def seed_plan_signatures(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM plansignaturesession WHERE token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  Plan signature sessions already exist, skipping.")
        return

    sigs = [
        PlanSignatureSession(
            profile_id=BOB_PROFILE_ID,
            ep_id="EP-B001",
            token="seed-ep-unsigned",
            expires_at=now + timedelta(hours=2),
        ),
        PlanSignatureSession(
            profile_id=BOB_PROFILE_ID,
            ep_id="EP-B002",
            token="seed-ep-signed",
            expires_at=now + timedelta(hours=24),
            signed_at=now - timedelta(hours=12),
        ),
    ]
    session.add_all(sigs)
    print("  Created 2 plan signature sessions: 1 unsigned, 1 signed")


async def seed_disclaimer(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM disclaimeracknowledgement WHERE session_id = 'seed-session'")
    )
    if result.scalar() > 0:
        print("  Disclaimer acknowledgement already exists, skipping.")
        return

    ack = DisclaimerAcknowledgement(session_id="seed-session", acknowledged_at=now)
    session.add(ack)
    print("  Created 1 disclaimer acknowledgement")


async def seed_audit_records(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM workerauditrecord WHERE worker_idir = :idir"),
        {"idir": WORKER_IDIR},
    )
    if result.scalar() > 0:
        print("  Audit records already exist, skipping.")
        return

    records = [
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/admin/clients", resource_type="client_search",
            timestamp=now - timedelta(hours=3), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/admin/clients/alice-bceid-1001",
            resource_type="client_profile", resource_id=ALICE_BCEID,
            client_bceid_guid=ALICE_BCEID,
            timestamp=now - timedelta(hours=2), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="POST /api/account/validate-pin",
            resource_type="pin_validation", resource_id=str(ALICE_USER_ID),
            client_bceid_guid=ALICE_BCEID,
            timestamp=now - timedelta(hours=1, minutes=30), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/service-requests",
            resource_type="sr_list", resource_id=str(BOB_USER_ID),
            client_bceid_guid=BOB_BCEID,
            timestamp=now - timedelta(hours=1), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SUPER_ADMIN",
            action="POST /api/admin/ao/validate",
            resource_type="ao_registration",
            timestamp=now - timedelta(minutes=30), request_ip="10.0.0.2",
        ),
    ]
    session.add_all(records)
    print("  Created 5 worker audit records")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

# Tables in FK-safe truncation order (children before parents)
TRUNCATE_ORDER = [
    "scanjob",
    "attachmentrecord",
    "plansignaturesession",
    "pinresettoken",
    "sr_drafts",
    "workerauditrecord",
    "disclaimeracknowledgement",
    "aoregistrationsession",
    "registrationsession",
    "profile",
    "user",
]


async def reset_seed_data(session: AsyncSession) -> None:
    """Truncate all seeded tables in FK-safe order."""
    print("\nResetting seed data...")
    for table in TRUNCATE_ORDER:
        await session.execute(text(f"DELETE FROM {table}"))
        print(f"  Cleared {table}")
    await session.commit()
    print("Reset complete.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(reset: bool = False) -> None:
    db_url = _get_db_url()
    print(f"Database: {db_url}")

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]

    async with async_session() as session:
        if reset:
            await reset_seed_data(session)

        print("\nSeeding database...")
        await seed_users(session)
        await seed_profiles(session)
        await seed_registration_sessions(session)
        await seed_pin_reset_tokens(session)
        await seed_ao_registration(session)
        await seed_sr_drafts(session)
        await seed_attachments(session)
        await seed_plan_signatures(session)
        await seed_disclaimer(session)
        await seed_audit_records(session)
        await session.commit()

    await engine.dispose()

    # Print summary
    print("\n" + "=" * 50)
    print("  SEED DATA SUMMARY")
    print("=" * 50)
    print()
    print("Personas:")
    print(f"  Alice Thompson  bceid_guid={ALICE_BCEID}  user_id={ALICE_USER_ID}")
    print(f"  Bob Chen        bceid_guid={BOB_BCEID}    user_id={BOB_USER_ID}")
    print(f"  Carol Williams  bceid_guid={CAROL_BCEID}  user_id={CAROL_USER_ID}")
    print(f"  Worker          idir={WORKER_IDIR}")
    print()
    print("JWT tokens (valid 24h — paste into Swagger UI Authorize dialog):")
    print()
    print(f"  Alice:  {_make_jwt(str(ALICE_USER_ID), 'CLIENT', bceid_guid=ALICE_BCEID)}")
    print()
    print(f"  Bob:    {_make_jwt(str(BOB_USER_ID), 'CLIENT', bceid_guid=BOB_BCEID)}")
    print()
    print(f"  Carol:  {_make_jwt(str(CAROL_USER_ID), 'CLIENT', bceid_guid=CAROL_BCEID)}")
    print()
    print(f"  Worker: {_make_jwt(WORKER_IDIR, 'WORKER', idir_username=WORKER_IDIR)}")
    print()
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the local development database")
    parser.add_argument("--reset", action="store_true", help="Truncate all seed data before re-inserting")
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset))
