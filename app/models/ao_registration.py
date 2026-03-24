"""Models for AO (Admin Override) Registration workflow."""
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SQLModel table
# ---------------------------------------------------------------------------


class AORegistrationSession(SQLModel, table=True):
    __tablename__ = "aoregistrationsession"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_token: UUID = Field(default_factory=uuid4, unique=True)
    worker_idir: str
    applicant_sr_num: str
    applicant_sin_hash: str  # bcrypt hash of SIN — never stored plaintext
    step_reached: int = 1
    expires_at: datetime
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class AOLoginRequest(BaseModel):
    sr_number: str
    sin: str


class AOSessionToken(BaseModel):
    session_token: str
    expires_at: datetime


class AORegistrationStep(BaseModel):
    step: int
    data: dict
