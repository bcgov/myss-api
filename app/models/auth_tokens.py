from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class PINResetToken(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    token: str = Field(unique=True)
    expires_at: datetime
    used_at: Optional[datetime] = None
