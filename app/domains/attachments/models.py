from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ScanStatus(str, Enum):
    PENDING = "PENDING"
    SCANNING = "SCANNING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"


class UploadResponse(BaseModel):
    scan_id: str  # UUID as string
    filename: str
    uploaded_at: datetime


class ScanStatusResponse(BaseModel):
    scan_id: str
    status: ScanStatus
    scanned_at: Optional[datetime] = None


class AttachmentSubmitRequest(BaseModel):
    scan_id: str
    filename: str


class AttachmentSubmitResponse(BaseModel):
    attachment_id: str
    sr_id: str
    filename: str


class ScanResultWebhookRequest(BaseModel):
    scan_id: str
    status: ScanStatus
    scanned_at: datetime
