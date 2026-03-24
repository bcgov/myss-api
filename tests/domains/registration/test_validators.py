# tests/domains/registration/test_validators.py
import pytest
from app.domains.registration.validators import (
    validate_sin,
    validate_phn,
    validate_name,
    validate_pin,
    validate_age,
)
from datetime import date


# BR-D1-02: SIN — Luhn algorithm
@pytest.mark.parametrize("sin,valid", [
    ("046 454 286", True),   # known valid Canadian SIN
    ("000000000",  False),   # all zeros
    ("123456789",  False),   # fails Luhn
    ("04645428",   False),   # too short (8 digits)
    ("abcdefghi",  False),   # non-numeric
])
def test_validate_sin(sin, valid):
    if valid:
        assert validate_sin(sin) == sin.replace(" ", "")
    else:
        with pytest.raises(ValueError):
            validate_sin(sin)


# BR-D1-03: PHN — MOD 11 checksum
@pytest.mark.parametrize("phn,valid", [
    ("9000000004", True),    # constructed valid BC PHN
    ("9000000005", False),   # constructed invalid BC PHN
    ("1234567890", False),   # known invalid
    ("",           True),    # PHN is optional — empty string passes (no error)
])
def test_validate_phn(phn, valid):
    if valid:
        result = validate_phn(phn)
        assert result == phn.replace(" ", "") or result == ""
    else:
        with pytest.raises(ValueError):
            validate_phn(phn)


# BR-D1-07: Name 2–50 chars, no numbers or special characters
@pytest.mark.parametrize("name,valid", [
    ("Mary",         True),
    ("O'Brien",      True),    # Apostrophes valid
    ("Jean-Pierre",  True),    # hyphen is allowed
    ("A",            False),   # too short
    ("X" * 51,       False),   # too long
    ("John3",        False),   # contains number
    ("Robert\x00Null", False), # null bytes must fail the regex
])
def test_validate_name(name, valid):
    if valid:
        assert validate_name(name) == name
    else:
        with pytest.raises(ValueError):
            validate_name(name)


# BR-D1-10: PIN exactly 4 numeric digits
@pytest.mark.parametrize("pin,valid", [
    ("1234", True),
    ("0000", True),
    ("123",  False),   # too short
    ("12345", False),  # too long
    ("12ab", False),   # non-numeric
])
def test_validate_pin(pin, valid):
    if valid:
        assert validate_pin(pin) == pin
    else:
        with pytest.raises(ValueError):
            validate_pin(pin)


# BR-D1-01: Must be at least 16 years old
def test_validate_age_too_young():
    dob = date.today().replace(year=date.today().year - 15)
    with pytest.raises(ValueError, match="16"):
        validate_age(dob)


def test_validate_age_exactly_16():
    dob = date.today().replace(year=date.today().year - 16)
    assert validate_age(dob) == dob


def test_validate_age_adult():
    dob = date(1990, 6, 15)
    assert validate_age(dob) == dob
