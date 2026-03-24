"""Registry that classifies SR types by their form requirements."""
from app.domains.service_requests.models import SRType

# SR types that have dynamic forms (most do); non-dynamic types use
# a simple submit-only flow with no form pages.
_DYNAMIC_TYPES: set[SRType] = {
    SRType.ASSIST,
    SRType.RREINSTATE,
    SRType.CRISIS_FOOD,
    SRType.CRISIS_SHELTER,
    SRType.CRISIS_CLOTHING,
    SRType.CRISIS_UTILITIES,
    SRType.CRISIS_MED_TRANSPORT,
    SRType.DIET,
    SRType.NATAL,
    SRType.MED_TRANSPORT_LOCAL,
    SRType.MED_TRANSPORT_NON_LOCAL,
    SRType.RECONSIDERATION,
    SRType.RECON_SUPPLEMENT,
    SRType.RECON_EXTENSION,
    SRType.STREAMLINED,
    SRType.PWD_DESIGNATION,
    SRType.PPMB,
}


# SR types that require auto-generated PDF on submit (e.g., crisis supplements,
# direct deposit, diet).
_PDF_TYPES: set[SRType] = {
    SRType.CRISIS_FOOD,
    SRType.CRISIS_SHELTER,
    SRType.CRISIS_CLOTHING,
    SRType.CRISIS_UTILITIES,
    SRType.CRISIS_MED_TRANSPORT,
    SRType.DIRECT_DEPOSIT,
    SRType.DIET,
    SRType.NATAL,
}


class SRTypeRegistry:
    @staticmethod
    def is_dynamic(sr_type: SRType) -> bool:
        return sr_type in _DYNAMIC_TYPES

    @staticmethod
    def requires_pdf(sr_type: SRType) -> bool:
        return sr_type in _PDF_TYPES
