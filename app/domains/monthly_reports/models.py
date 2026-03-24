from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SD81Status(str, Enum):
    PARTIAL = "PRT"
    SUBMITTED = "SUB"
    RESTARTED = "RST"
    RESUBMITTED = "RES"
    PENDING_DOCUMENTS = "PND"


class ChequeScheduleWindow(BaseModel):
    benefit_month: date
    income_date: date
    cheque_issue_date: date
    period_close_date: datetime  # Friday 4PM


class SD81Summary(BaseModel):
    sd81_id: str
    benefit_month: date
    status: SD81Status
    submitted_at: Optional[datetime] = None


class SD81ListResponse(BaseModel):
    reports: list[SD81Summary]
    total: int


class SD81SubmitRequest(BaseModel):
    pin: str
    spouse_pin: str | None = None


class SD81SubmitResponse(BaseModel):
    sd81_id: str
    status: SD81Status
    submitted_at: datetime
