from datetime import datetime, UTC
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class SRDraft(SQLModel, table=True):
    __tablename__ = "sr_drafts"

    sr_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=36)
    sr_type: str = Field(max_length=50)
    draft_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
