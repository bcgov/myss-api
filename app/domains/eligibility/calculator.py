# app/domains/eligibility/calculator.py
from decimal import Decimal
from app.domains.eligibility.models import (
    AssetLimitRow,
    EligibilityRequest,
    EligibilityResponse,
    RateRow,
    RelationshipStatus,
)

# Maximum family size tracked in rate table (BR-D9-03 / OQ-D9-02: cap at 7)
MAX_RATE_TABLE_FAMILY_SIZE = 7


class EligibilityCalculatorService:
    """Pure calculation service — no I/O, no external dependencies.

    Implements BR-D9-01 through BR-D9-09 from the functional analysis.
    """

    def __init__(
        self,
        income_rates: list[RateRow],
        asset_limits: list[AssetLimitRow],
    ) -> None:
        # Index by family_size for O(1) lookup
        self._income_rates: dict[int, RateRow] = {r.family_size: r for r in income_rates}
        self._asset_limits: dict[str, Decimal] = {r.limit_type: r.limit for r in asset_limits}

    # ------------------------------------------------------------------
    # BR-D9-04: Client type classification
    # ------------------------------------------------------------------
    def _classify_client_type(self, req: EligibilityRequest) -> str:
        """Return client type code A–E per BR-D9-04."""
        is_couple = req.relationship_status == RelationshipStatus.COUPLE
        has_dependants = req.num_dependants > 0
        kp_pwd = req.applicant_pwd
        sp_pwd = req.spouse_pwd

        if is_couple:
            if kp_pwd and sp_pwd:
                return "E"
            if kp_pwd or sp_pwd:
                return "C"
            return "A"
        else:
            # single
            if has_dependants:
                return "D" if kp_pwd else "B"
            return "C" if kp_pwd else "A"

    # ------------------------------------------------------------------
    # BR-D9-06: Asset limit category
    # ------------------------------------------------------------------
    def _asset_limit_category(self, req: EligibilityRequest) -> str:
        """Return asset limit category per BR-D9-06."""
        is_couple = req.relationship_status == RelationshipStatus.COUPLE
        has_dependants = req.num_dependants > 0
        kp_pwd = req.applicant_pwd
        sp_pwd = req.spouse_pwd

        if kp_pwd and sp_pwd:
            return "D"  # both PWD
        if kp_pwd or sp_pwd:
            return "C"  # at least one PWD
        if is_couple or has_dependants:
            return "B"  # married or has dependant
        return "A"  # single, no dependants, not PWD

    # ------------------------------------------------------------------
    # BR-D9-05: Income limit lookup
    # ------------------------------------------------------------------
    def _get_income_limit(self, client_type: str, family_size: int) -> Decimal:
        capped = min(family_size, MAX_RATE_TABLE_FAMILY_SIZE)
        row = self._income_rates[capped]
        return getattr(row, f"type_{client_type.lower()}")

    # ------------------------------------------------------------------
    # BR-D9-07/08: Core calculation
    # ------------------------------------------------------------------
    def calculate(self, req: EligibilityRequest) -> EligibilityResponse:
        """Calculate eligibility per BR-D9-07 and BR-D9-08."""
        client_type = self._classify_client_type(req)
        asset_cat = self._asset_limit_category(req)
        asset_limit = self._asset_limits[asset_cat]

        # BR-D9-07: asset gate
        if req.total_assets > asset_limit:
            return EligibilityResponse(
                eligible=False,
                estimated_amount=Decimal("0.00"),
                ineligibility_reason="assets_exceed_limit",
                client_type=client_type,
            )

        income_limit = self._get_income_limit(client_type, req.family_size)

        # BR-D9-08: benefit = income_limit - monthly_income; floor at 0
        benefit = income_limit - req.total_income
        if benefit <= Decimal("0"):
            return EligibilityResponse(
                eligible=False,
                estimated_amount=Decimal("0.00"),
                ineligibility_reason="income_exceeds_limit",
                client_type=client_type,
            )

        return EligibilityResponse(
            eligible=True,
            estimated_amount=benefit,
            ineligibility_reason=None,
            client_type=client_type,
        )
