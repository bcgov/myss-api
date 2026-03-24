from uuid import UUID, uuid4
from datetime import datetime, UTC
from typing import Optional
from sqlmodel import SQLModel, Field


class AttachmentRecord(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    sr_draft_id: Optional[str] = Field(default=None, foreign_key="sr_drafts.sr_id")
    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str  # S3 key or PVC path; never a local filesystem path
    av_status: str  # AVStatus enum: PENDING, CLEAN, INFECTED
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScanJob(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    attachment_id: UUID = Field(foreign_key="attachmentrecord.id", unique=True)
    status: str  # ScanStatus enum: QUEUED, SCANNING, CLEAN, INFECTED
    scanned_at: Optional[datetime] = None
