from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class BenefitCode(int, Enum):
    HOUSING_STABILITY_SUPPLEMENT = 32
    SUPPORT = 41
    SHELTER = 42
    HARDSHIP_COMFORTS = 73


class AllowanceItem(BaseModel):
    code: BenefitCode
    amount: Decimal
    description: str


class DeductionItem(BaseModel):
    code: str
    amount: Decimal
    description: str


class SupplementItem(BaseModel):
    code: str
    amount: Decimal
    effective_date: date


class ServiceProviderPayment(BaseModel):
    provider_name: str
    amount: Decimal
    payment_date: date


class MISPaymentData(BaseModel):
    mis_person_id: str
    key_player_name: str
    spouse_name: str | None
    payment_method: str
    payment_distribution: str
    allowances: list[AllowanceItem]
    deductions: list[DeductionItem]
    aee_balance: Decimal | None


class PaymentInfoResponse(BaseModel):
    upcoming_benefit_date: date
    assistance_type: str
    supplements: list[SupplementItem]
    service_provider_payments: list[ServiceProviderPayment]
    mis_data: MISPaymentData


# ChequeScheduleResponse is the same shape as ChequeScheduleWindow (shared DTO)
from app.domains.shared.models import ChequeScheduleWindow
ChequeScheduleResponse = ChequeScheduleWindow


class T5Slip(BaseModel):
    tax_year: int
    box_10_amount: Decimal
    box_11_amount: Decimal
    available: bool


class T5SlipList(BaseModel):
    slips: list[T5Slip]
