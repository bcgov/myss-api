# tests/domains/registration/test_schemas.py
import pytest
from pydantic import ValidationError
from app.domains.registration.schemas import (
    PersonalInfoRequest,
    PinRequest,
    StartRegistrationRequest,
)
from app.domains.registration.models import AccountCreationType


# StartRegistrationRequest
def test_start_registration_valid_self():
    req = StartRegistrationRequest(account_creation_type=AccountCreationType.SELF)
    assert req.account_creation_type == AccountCreationType.SELF


def test_start_registration_invalid_type():
    with pytest.raises(ValidationError):
        StartRegistrationRequest(account_creation_type="GARBAGE")


# PersonalInfoRequest — BR-D1-05/06: email match
def test_personal_info_email_mismatch_raises():
    with pytest.raises(ValidationError, match="email"):
        PersonalInfoRequest(
            first_name="Mary",
            last_name="Smith",
            email="mary@example.com",
            email_confirm="other@example.com",
            sin="046454286",
            date_of_birth="1990-05-15",
            gender="F",
            phone_number="2505551234",
            phone_type="CELL",
            has_open_case=False,
        )


def test_personal_info_valid():
    req = PersonalInfoRequest(
        first_name="Mary",
        last_name="Smith",
        email="mary@example.com",
        email_confirm="mary@example.com",
        sin="046454286",
        date_of_birth="1990-05-15",
        gender="F",
        phone_number="2505551234",
        phone_type="CELL",
        has_open_case=False,
    )
    assert req.first_name == "Mary"
    assert req.sin == "046454286"


# BR-D1-02: SIN validation in schema
def test_personal_info_invalid_sin():
    with pytest.raises(ValidationError, match="SIN"):
        PersonalInfoRequest(
            first_name="Mary",
            last_name="Smith",
            email="mary@example.com",
            email_confirm="mary@example.com",
            sin="123456789",  # invalid Luhn
            date_of_birth="1990-05-15",
            gender="F",
            phone_number="2505551234",
            phone_type="CELL",
            has_open_case=False,
        )


# BR-D1-01: Age validation in schema
def test_personal_info_too_young():
    from datetime import date
    young_dob = date.today().replace(year=date.today().year - 14).isoformat()
    with pytest.raises(ValidationError, match="16"):
        PersonalInfoRequest(
            first_name="Mary",
            last_name="Smith",
            email="mary@example.com",
            email_confirm="mary@example.com",
            sin="046454286",
            date_of_birth=young_dob,
            gender="F",
            phone_number="2505551234",
            phone_type="CELL",
            has_open_case=False,
        )


# BR-D1-10: PIN validation in schema
def test_pin_request_valid():
    req = PinRequest(pin="1234", pin_confirm="1234")
    assert req.pin == "1234"


def test_pin_request_mismatch():
    with pytest.raises(ValidationError, match="PIN"):
        PinRequest(pin="1234", pin_confirm="5678")


def test_pin_request_non_numeric():
    with pytest.raises(ValidationError, match="4 digits"):
        PinRequest(pin="12ab", pin_confirm="12ab")


def test_pin_request_too_short():
    with pytest.raises(ValidationError, match="4 digits"):
        PinRequest(pin="123", pin_confirm="123")
