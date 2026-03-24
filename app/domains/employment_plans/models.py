from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from enum import Enum


class EPStatus(str, Enum):
    RECEIVED = "Received"
    SUBMITTED = "Submitted"
    PENDING_SIGNATURE = "PendingSignature"


class EmploymentPlan(BaseModel):
    ep_id: int
    message_id: int | None = None
    icm_attachment_id: str
    status: EPStatus
    plan_date: date
    message_deleted: bool


class EPListResponse(BaseModel):
    plans: list[EmploymentPlan]


class EPDetailResponse(EmploymentPlan):
    pass  # Same fields for now; detail may add more later


class EPSignRequest(BaseModel):
    pin: str = Field(min_length=1)
    message_id: int


class EPSignResponse(BaseModel):
    ep_id: int
    signed_at: datetime
