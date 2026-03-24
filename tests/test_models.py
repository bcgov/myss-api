import pytest
from sqlmodel import SQLModel, create_engine, inspect as sql_inspect, Session
from sqlalchemy import inspect as sa_inspect


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    from app.models import (
        User, Profile, RegistrationSession, SRDraft, AttachmentRecord,
        ScanJob, PlanSignatureSession, PINResetToken, WorkerAuditRecord,
        AORegistrationSession, DisclaimerAcknowledgement,
    )
    SQLModel.metadata.create_all(eng)
    return eng


def test_all_tables_created(engine):
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "user", "profile", "registrationsession", "sr_drafts",
        "attachmentrecord", "scanjob", "plansignaturesession",
        "pinresettoken", "workerauditrecord",
        "aoregistrationsession", "disclaimeracknowledgement",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_nullable_fields(engine):
    inspector = sa_inspect(engine)
    # RegistrationSession.user_id must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("registrationsession")}
    assert cols["user_id"]["nullable"] is True
    # SRDraft.draft_json must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("sr_drafts")}
    assert cols["draft_json"]["nullable"] is True
    # PINResetToken.used_at must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("pinresettoken")}
    assert cols["used_at"]["nullable"] is True
    # AttachmentRecord.sr_draft_id must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("attachmentrecord")}
    assert cols["sr_draft_id"]["nullable"] is True
    # ScanJob.scanned_at must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("scanjob")}
    assert cols["scanned_at"]["nullable"] is True
    # PlanSignatureSession.signed_at must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("plansignaturesession")}
    assert cols["signed_at"]["nullable"] is True
    # AORegistrationSession.applicant_sr_num must NOT be nullable (set on login)
    cols = {c["name"]: c for c in inspector.get_columns("aoregistrationsession")}
    assert cols["applicant_sr_num"]["nullable"] is False
    # AORegistrationSession.completed_at must be nullable
    assert cols["completed_at"]["nullable"] is True
    # RegistrationSession.completed_at must be nullable
    cols = {c["name"]: c for c in inspector.get_columns("registrationsession")}
    assert cols["completed_at"]["nullable"] is True
