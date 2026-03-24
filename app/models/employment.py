from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class PlanSignatureSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    ep_id: str  # ICM employment plan ID (opaque reference)
    token: str = Field(unique=True)
    expires_at: datetime
    signed_at: Optional[datetime] = None
