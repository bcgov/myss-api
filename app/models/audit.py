from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class WorkerAuditRecord(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    worker_idir: str = Field(index=True)
    worker_role: str = ""  # WorkerRole value
    action: str  # HTTP method + path
    resource_type: str = ""
    resource_id: Optional[str] = None
    client_bceid_guid: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_ip: str = ""
