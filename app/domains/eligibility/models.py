# app/domains/eligibility/models.py
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator, Field


class RelationshipStatus(str, Enum):
    SINGLE = "SINGLE"
    COUPLE = "COUPLE"


class EligibilityRequest(BaseModel):
    relationship_status: RelationshipStatus
    num_dependants: int = Field(ge=0, le=20)
    applicant_pwd: bool
    spouse_pwd: bool = False
    monthly_income: Decimal = Field(ge=Decimal("0"))
    spouse_monthly_income: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))
    primary_vehicle_value: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))
    other_vehicle_value: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))
    other_asset_value: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))

    @model_validator(mode="after")
    def spouse_fields_require_couple(self) -> "EligibilityRequest":
        if self.relationship_status == RelationshipStatus.SINGLE:
            if self.spouse_pwd:
                raise ValueError("spouse_pwd requires COUPLE relationship_status")
            if self.spouse_monthly_income > 0:
                raise ValueError("spouse_monthly_income requires COUPLE relationship_status")
        return self

    @property
    def family_size(self) -> int:
        adults = 2 if self.relationship_status == RelationshipStatus.COUPLE else 1
        return adults + self.num_dependants

    @property
    def total_assets(self) -> Decimal:
        return self.primary_vehicle_value + self.other_vehicle_value + self.other_asset_value

    @property
    def total_income(self) -> Decimal:
        return self.monthly_income + self.spouse_monthly_income


class EligibilityResponse(BaseModel):
    eligible: bool
    estimated_amount: Decimal
    ineligibility_reason: Optional[str] = None
    client_type: str  # "A", "B", "C", "D", or "E" — for transparency


class RateRow(BaseModel):
    """One row of the EligibilityRateTable for a given family_size."""
    family_size: int = Field(ge=1)
    type_a: Decimal
    type_b: Decimal
    type_c: Decimal
    type_d: Decimal
    type_e: Decimal


class AssetLimitRow(BaseModel):
    """Asset limit for a given client asset limit category."""
    limit_type: str  # "A", "B", "C", "D"
    limit: Decimal
