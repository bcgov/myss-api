# app/domains/registration/schemas.py
"""
Pydantic request/response models for the registration wizard API.

Each step has a dedicated request model with inline validation via
@field_validator and @model_validator, replacing the scattered
validation in RegisterViewModel.Save() and client-side jQuery Validation.
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

from app.domains.registration.models import AccountCreationType, Gender, PhoneType
from app.domains.registration.validators import (
    validate_age,
    validate_name,
    validate_pin,
    validate_phn,
    validate_sin,
)


# ---------------------------------------------------------------------------
# Step 1: Start registration
# ---------------------------------------------------------------------------
class StartRegistrationRequest(BaseModel):
    account_creation_type: AccountCreationType


class StartRegistrationResponse(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Step state reader response
# ---------------------------------------------------------------------------
class StepStateResponse(BaseModel):
    token: str
    step_reached: int
    account_creation_type: AccountCreationType


# ---------------------------------------------------------------------------
# Step 2: Personal information
# ---------------------------------------------------------------------------
class SpouseInfoRequest(BaseModel):
    """Spouse personal information — required when applicant is in a couple (BR-D1-08)."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    sin: str
    phn: Optional[str] = None
    date_of_birth: date
    gender: Gender

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("sin")
    @classmethod
    def validate_sin_field(cls, v: str) -> str:
        return validate_sin(v)

    @field_validator("phn")
    @classmethod
    def validate_phn_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phn(v) or None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return validate_age(v)


class OpenCaseIdentificationRequest(BaseModel):
    """Supplementary fields for existing clients declaring an open case (BR-D1-20)."""
    last_assistance_payment_amount: Optional[str] = None  # mandatory when has_open_case=True
    has_drivers_licence: bool = False
    drivers_licence_expiry: Optional[date] = None
    has_previous_address: bool = False
    previous_address: Optional[str] = None
    paying_service_providers: bool = False
    service_providers_description: Optional[str] = None
    # BR-D1-20: payment_method options confirmed from ICM code table at runtime
    payment_method: Optional[str] = None


class PersonalInfoRequest(BaseModel):
    first_name: str
    middle_name: Optional[str] = None    # OQ-D1-11: likely optional despite FDD "Mandatory: Yes"
    last_name: str
    email: str
    email_confirm: str
    sin: str
    phn: Optional[str] = None
    date_of_birth: date
    gender: Gender
    phone_number: str
    phone_type: PhoneType
    has_open_case: bool = False
    open_case_identification: Optional[OpenCaseIdentificationRequest] = None
    spouse: Optional[SpouseInfoRequest] = None    # required when COUPLE (BR-D1-08)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_field(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("middle_name")
    @classmethod
    def validate_middle_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return validate_name(v)

    @field_validator("sin")
    @classmethod
    def validate_sin_field(cls, v: str) -> str:
        return validate_sin(v)

    @field_validator("phn")
    @classmethod
    def validate_phn_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phn(v) or None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return validate_age(v)

    @model_validator(mode="after")
    def email_must_match(self) -> "PersonalInfoRequest":
        """BR-D1-06: email and email_confirm must be identical."""
        if self.email != self.email_confirm:
            raise ValueError("email and email_confirm must match")
        return self

    @model_validator(mode="after")
    def open_case_payment_mandatory(self) -> "PersonalInfoRequest":
        """BR-D1-20: last_assistance_payment_amount mandatory when has_open_case=True."""
        if self.has_open_case and self.open_case_identification:
            if not self.open_case_identification.last_assistance_payment_amount:
                raise ValueError(
                    "last_assistance_payment_amount is required when has_open_case is True"
                )
        return self


class PersonalInfoResponse(BaseModel):
    next_step: int


# ---------------------------------------------------------------------------
# Step 4: PIN creation
# ---------------------------------------------------------------------------
class PinRequest(BaseModel):
    pin: str
    pin_confirm: str

    @field_validator("pin", "pin_confirm")
    @classmethod
    def validate_pin_field(cls, v: str) -> str:
        return validate_pin(v)

    @model_validator(mode="after")
    def pins_must_match(self) -> "PinRequest":
        """BR-D1-10: PIN and PIN confirm must be identical."""
        if self.pin != self.pin_confirm:
            raise ValueError("PIN and PIN confirmation do not match")
        return self


class PinResponse(BaseModel):
    next_step: int


# ---------------------------------------------------------------------------
# Step 5/6: BCeID link
# ---------------------------------------------------------------------------
class BCeIDLinkRequest(BaseModel):
    """Receives the BCeID identity claim from Auth.js after OIDC redirect."""
    bceid_guid: str
    bceid_username: str
    program_type: str = "EA"  # always EA for income assistance


class BCeIDLinkResponse(BaseModel):
    user_id: int
    profile_id: int
    icm_sr_number: Optional[str] = None
    next_step: int = 6
