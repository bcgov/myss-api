from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class PhoneNumberOperation(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class PhoneNumberUpdate(BaseModel):
    phone_id: int | None = None
    phone_number: str = ""
    phone_type: str = ""
    operation: PhoneNumberOperation

    @model_validator(mode="after")
    def delete_requires_phone_id(self):
        if self.operation == PhoneNumberOperation.DELETE and self.phone_id is None:
            raise ValueError("phone_id is required for DELETE operation")
        return self


class UpdateContactRequest(BaseModel):
    email: str | None = None
    email_confirm: str | None = None
    phones: list[PhoneNumberUpdate] = Field(default_factory=list)

    @model_validator(mode="after")
    def emails_must_match(self):
        if self.email and self.email != self.email_confirm:
            raise ValueError("email and email_confirm must match")
        return self


class AccountInfoResponse(BaseModel):
    user_id: str
    email: str | None = None
    phone_numbers: list[dict] = Field(default_factory=list)
    case_number: str | None = None
    case_status: str | None = None


class CaseMember(BaseModel):
    name: str
    relationship: str


class CaseMemberListResponse(BaseModel):
    members: list[CaseMember]


# PIN models
class PINValidateRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class PINChangeRequest(BaseModel):
    current_pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    new_pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class PINResetRequest(BaseModel):
    email: str


class PINResetConfirmRequest(BaseModel):
    token: str
    new_pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
