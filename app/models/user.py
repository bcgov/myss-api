from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    bceid_guid: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Profile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    portal_id: str = Field(unique=True, index=True)
    link_code: str  # LinkStatus enum: LINKED, UNLINKED, PENDING
    mis_person_id: str  # opaque FK to MIS PORTALSERVICES; never interpreted by MySS
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
