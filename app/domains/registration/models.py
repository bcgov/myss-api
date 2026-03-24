# app/domains/registration/models.py
from datetime import datetime, date
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


class AccountCreationType(str, Enum):
    SELF = "SELF"
    WITH_HELPER = "WITH_HELPER"
    POA = "POA"
    PARENT = "PARENT"


class LinkStatus(str, Enum):
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"
    PENDING = "PENDING"


class RegistrationStep(int, Enum):
    ACCOUNT_TYPE = 1
    PERSONAL_INFO = 2
    EMAIL_VERIFY = 3
    PIN_CREATION = 4
    BCEID_LINK = 5
    COMPLETE = 6


class RegistrationSessionState(BaseModel):
    """In-memory representation of a registration_sessions row."""
    token: str
    account_creation_type: AccountCreationType
    step_reached: int
    poa_data: Optional[dict[str, Any]] = None
    registrant_data: Optional[dict[str, Any]] = None
    spouse_data: Optional[dict[str, Any]] = None
    invite_token: Optional[str] = None
    invite_token_used: bool = False
    pin_hash: Optional[str] = None
    pin_salt: Optional[str] = None
    user_id: Optional[int] = None
    expires_at: datetime


class PhoneType(str, Enum):
    HOME = "HOME"
    CELL = "CELL"
    WORK = "WORK"
    MESSAGE = "MESSAGE"


class Gender(str, Enum):
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"
