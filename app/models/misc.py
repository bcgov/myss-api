from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field


class DisclaimerAcknowledgement(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: str  # anonymous session identifier
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
