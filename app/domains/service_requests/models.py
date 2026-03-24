from datetime import datetime
from enum import Enum
from pydantic import BaseModel, field_validator
from typing import Optional


class SRType(str, Enum):
    ASSIST = "ASSIST"
    RREINSTATE = "RREINSTATE"
    CRISIS_FOOD = "CRISIS_FOOD"
    CRISIS_SHELTER = "CRISIS_SHELTER"
    CRISIS_CLOTHING = "CRISIS_CLOTHING"
    CRISIS_UTILITIES = "CRISIS_UTILITIES"
    CRISIS_MED_TRANSPORT = "CRISIS_MED_TRANSPORT"
    DIRECT_DEPOSIT = "DIRECT_DEPOSIT"
    DIET = "DIET"
    NATAL = "NATAL"
    MED_TRANSPORT_LOCAL = "MED_TRANSPORT_LOCAL"
    MED_TRANSPORT_NON_LOCAL = "MED_TRANSPORT_NON_LOCAL"
    RECONSIDERATION = "RECONSIDERATION"
    RECON_SUPPLEMENT = "RECON_SUPPLEMENT"
    RECON_EXTENSION = "RECON_EXTENSION"
    STREAMLINED = "STREAMLINED"
    BUS_PASS = "BUS_PASS"
    PWD_DESIGNATION = "PWD_DESIGNATION"
    PPMB = "PPMB"


class SRSummary(BaseModel):
    sr_id: str
    sr_type: SRType
    sr_number: str
    status: str
    client_name: str
    created_at: datetime


class SRListResponse(BaseModel):
    items: list[SRSummary]
    total: int
    page: int
    page_size: int


class SRTypeMetadata(BaseModel):
    sr_type: SRType
    display_name: str
    requires_pin: bool
    has_attachments: bool
    max_active: int


class SRCreateRequest(BaseModel):
    sr_type: SRType


class SRDraftResponse(BaseModel):
    sr_id: str
    sr_type: SRType
    draft_json: Optional[dict] = None
    updated_at: datetime


class DynamicFormType(str, Enum):
    SR = "SR"
    MONTHLY_REPORT = "MONTHLY_REPORT"
    APPLICATION = "APPLICATION"


class DynamicFormField(BaseModel):
    field_id: str
    label: str
    field_type: str  # text, number, date, select, checkbox, textarea
    required: bool = False
    options: Optional[list[str]] = None
    validation: Optional[dict] = None


class DynamicFormPage(BaseModel):
    page_index: int
    title: str
    fields: list[DynamicFormField]


class DynamicFormSchema(BaseModel):
    form_type: DynamicFormType
    sr_type: Optional[SRType] = None
    pages: list[DynamicFormPage]
    total_pages: int


class SRFormUpdateRequest(BaseModel):
    answers: dict
    page_index: int


class SRSubmitRequest(BaseModel):
    pin: str
    spouse_pin: str | None = None
    declaration_accepted: bool

    @field_validator("declaration_accepted")
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Declaration must be accepted")
        return v


class SRSubmitResponse(BaseModel):
    sr_id: str
    sr_number: str
    submitted_at: datetime


class SRDetailResponse(BaseModel):
    sr_id: str
    sr_type: SRType
    sr_number: str
    status: str
    client_name: str
    created_at: datetime
    answers: dict | None = None
    attachments: list[str] = []


class SRWithdrawRequest(BaseModel):
    reason: str | None = None
