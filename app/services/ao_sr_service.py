"""AO Service Request Service — handles AO dynamic form submission."""
from app.models.ao_registration import AORegistrationSession
from app.services.icm.admin import SiebelAdminClient


class AOSRService:
    """Service for AO (Admin Override) dynamic form/SR submission.

    Worker identity from the AO session is used as the form signature.
    No client PIN is required.
    """

    def __init__(self, admin_client: SiebelAdminClient | None = None) -> None:
        self._admin_client = admin_client

    async def submit_ao_form(
        self,
        sr_id: str,
        form_data: dict,
        session: AORegistrationSession,
    ) -> dict:
        """Submit an AO dynamic form.

        Uses worker identity from session for signature — no PIN required.

        Stub implementation: returns confirmation payload.
        """
        # TODO: Replace with real ICM call when endpoint is available
        # e.g. await self._admin_client.submit_ao_form(sr_id, form_data, session.worker_idir)
        return {
            "sr_id": sr_id,
            "status": "submitted",
            "submitted_by": session.worker_idir,
            "applicant_sr_num": session.applicant_sr_num,
        }
