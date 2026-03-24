# tests/domains/eligibility/test_calculator.py
import pytest
from decimal import Decimal
from app.domains.eligibility.models import (
    EligibilityRequest,
    EligibilityResponse,
    RelationshipStatus,
    RateRow,
    AssetLimitRow,
)
from app.domains.eligibility.calculator import EligibilityCalculatorService


# Minimal synthetic rate table matching FDD BR-D9-05 and BR-D9-06
def make_rates() -> list[RateRow]:
    # family_size, type_a, type_b, type_c, type_d, type_e
    return [
        RateRow(family_size=1,  type_a=Decimal("1060.00"),  type_b=Decimal("0"),       type_c=Decimal("1535.50"), type_d=Decimal("0"),       type_e=Decimal("0")),
        RateRow(family_size=2,  type_a=Decimal("1650.00"),  type_b=Decimal("1405.00"), type_c=Decimal("2125.50"), type_d=Decimal("1880.50"), type_e=Decimal("2652.50")),
        RateRow(family_size=3,  type_a=Decimal("1845.00"),  type_b=Decimal("1500.00"), type_c=Decimal("2320.50"), type_d=Decimal("1975.50"), type_e=Decimal("2847.50")),
        RateRow(family_size=4,  type_a=Decimal("1895.00"),  type_b=Decimal("1550.00"), type_c=Decimal("2370.50"), type_d=Decimal("2025.50"), type_e=Decimal("2897.50")),
        RateRow(family_size=5,  type_a=Decimal("1945.00"),  type_b=Decimal("1600.00"), type_c=Decimal("2420.50"), type_d=Decimal("2075.50"), type_e=Decimal("2947.50")),
        RateRow(family_size=6,  type_a=Decimal("1995.00"),  type_b=Decimal("1650.00"), type_c=Decimal("2470.50"), type_d=Decimal("2125.50"), type_e=Decimal("2997.50")),
        RateRow(family_size=7,  type_a=Decimal("2045.00"),  type_b=Decimal("1700.00"), type_c=Decimal("2520.50"), type_d=Decimal("2175.50"), type_e=Decimal("3047.50")),
    ]


def make_asset_limits() -> list[AssetLimitRow]:
    return [
        AssetLimitRow(limit_type="A", limit=Decimal("5000.00")),
        AssetLimitRow(limit_type="B", limit=Decimal("10000.00")),
        AssetLimitRow(limit_type="C", limit=Decimal("100000.00")),
        AssetLimitRow(limit_type="D", limit=Decimal("200000.00")),
    ]


@pytest.fixture
def svc() -> EligibilityCalculatorService:
    return EligibilityCalculatorService(income_rates=make_rates(), asset_limits=make_asset_limits())


# BR-D9-08: basic eligible single person, no dependants, no PWD
def test_single_no_dependants_eligible(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=0,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("800.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    assert result.eligible is True
    assert result.estimated_amount == Decimal("260.00")  # 1060 - 800
    assert result.ineligibility_reason is None


# BR-D9-08: income exceeds limit → $0, but still eligible (non-zero limit exists)
def test_single_income_exceeds_limit(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=0,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("1200.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    assert result.eligible is False
    assert result.estimated_amount == Decimal("0.00")
    assert result.ineligibility_reason == "income_exceeds_limit"


# BR-D9-07: assets exceed limit → $0 regardless of income
def test_assets_exceed_limit(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=0,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("500.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("3000.00"),
        other_vehicle_value=Decimal("1000.00"),
        other_asset_value=Decimal("1500.00"),  # total = 5500 > 5000 limit
    )
    result = svc.calculate(req)
    assert result.eligible is False
    assert result.estimated_amount == Decimal("0.00")
    assert result.ineligibility_reason == "assets_exceed_limit"


# BR-D9-04: Type C — single, no dependants, PWD
def test_single_pwd_type_c(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=0,
        applicant_pwd=True,
        spouse_pwd=False,
        monthly_income=Decimal("1000.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    assert result.eligible is True
    assert result.estimated_amount == Decimal("535.50")  # 1535.50 - 1000


# BR-D9-04: Type A — married, neither PWD, family size 2
def test_married_no_pwd_type_a(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.COUPLE,
        num_dependants=0,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("800.00"),
        spouse_monthly_income=Decimal("400.00"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    # family_size=2, type_a=1650; combined income=1200
    assert result.eligible is True
    assert result.estimated_amount == Decimal("450.00")  # 1650 - 1200


# BR-D9-04: Type B — single with 1 dependant, not PWD, family_size=2
def test_single_with_dependant_type_b(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=1,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("1000.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    # family_size=2, type_b=1405
    assert result.eligible is True
    assert result.estimated_amount == Decimal("405.00")  # 1405 - 1000


# BR-D9-04: Type E — married, both KP and spouse are PWD, family_size=2
def test_married_both_pwd_type_e(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.COUPLE,
        num_dependants=0,
        applicant_pwd=True,
        spouse_pwd=True,
        monthly_income=Decimal("1000.00"),
        spouse_monthly_income=Decimal("500.00"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    # family_size=2, type_e=2652.50; combined income=1500
    assert result.eligible is True
    assert result.estimated_amount == Decimal("1152.50")


# BR-D9-03: family_size cap at 7 for family_size > 7
def test_family_size_capped_at_7(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.SINGLE,
        num_dependants=9,  # family_size = 1 + 9 = 10; should use row 7
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("1000.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("0"),
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    # single with dependants = type_b; family_size capped at 7 → type_b=1700
    assert result.eligible is True
    assert result.estimated_amount == Decimal("700.00")


# BR-D9-06: Type A asset limit is 5000 (single, no dependants, not PWD)
# Type B asset limit is 10000 (married or at least one dependant)
def test_asset_limit_type_b_married(svc):
    req = EligibilityRequest(
        relationship_status=RelationshipStatus.COUPLE,
        num_dependants=0,
        applicant_pwd=False,
        spouse_pwd=False,
        monthly_income=Decimal("500.00"),
        spouse_monthly_income=Decimal("0"),
        primary_vehicle_value=Decimal("6000.00"),  # > 5000 type_a limit, < 10000 type_b
        other_vehicle_value=Decimal("0"),
        other_asset_value=Decimal("0"),
    )
    result = svc.calculate(req)
    # married uses type_b asset limit=10000; 6000 < 10000 → eligible
    assert result.eligible is True


@pytest.mark.parametrize("family_size,income_limit", [
    (1, Decimal("1060.00")),
    (2, Decimal("1650.00")),
    (3, Decimal("1845.00")),
    (4, Decimal("1895.00")),
    (5, Decimal("1945.00")),
    (6, Decimal("1995.00")),
    (7, Decimal("2045.00")),
])
def test_type_a_income_limits_parametrized(svc, family_size, income_limit):
    """BR-D9-05: all Type A income limits from the rate table."""
    dependants = family_size - 1  # single adult + N dependants → type_a only when no dependants...
    # For family_size>=2 with single adult, use married couple to hit type_a
    if family_size == 1:
        req = EligibilityRequest(
            relationship_status=RelationshipStatus.SINGLE,
            num_dependants=0,
            applicant_pwd=False, spouse_pwd=False,
            monthly_income=Decimal("0"), spouse_monthly_income=Decimal("0"),
            primary_vehicle_value=Decimal("0"), other_vehicle_value=Decimal("0"),
            other_asset_value=Decimal("0"),
        )
    else:
        req = EligibilityRequest(
            relationship_status=RelationshipStatus.COUPLE,
            num_dependants=family_size - 2,
            applicant_pwd=False, spouse_pwd=False,
            monthly_income=Decimal("0"), spouse_monthly_income=Decimal("0"),
            primary_vehicle_value=Decimal("0"), other_vehicle_value=Decimal("0"),
            other_asset_value=Decimal("0"),
        )
    result = svc.calculate(req)
    assert result.estimated_amount == income_limit
