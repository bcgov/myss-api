from datetime import datetime, timezone
from typing import Optional

from app.services.icm.service_requests import SiebelSRClient
from app.domains.account.pin_service import PINService
from app.domains.service_requests.draft_repository import SRDraftRepository
from app.domains.service_requests.models import (
    SRSummary,
    SRListResponse,
    SRTypeMetadata,
    SRType,
    SRDraftResponse,
    SRSubmitResponse,
    SRDetailResponse,
    DynamicFormType,
    DynamicFormField,
    DynamicFormPage,
    DynamicFormSchema,
)
from app.domains.service_requests.sr_type_registry import SRTypeRegistry


class ServiceRequestService:
    def __init__(
        self,
        sr_client: SiebelSRClient,
        draft_repo: SRDraftRepository | None = None,
        pin_service: PINService | None = None,
    ):
        self._client = sr_client
        self._draft_repo = draft_repo
        self._pin_service = pin_service

    async def list_srs(self, profile_id: str, page: int = 1, page_size: int = 20) -> SRListResponse:
        raw = await self._client.get_sr_list(profile_id)
        items_raw = raw.get("items", [])
        items = [SRSummary(**item) for item in items_raw]
        total = raw.get("total", len(items))
        return SRListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_eligible_types(self, profile_id: str, case_status: str) -> list[SRTypeMetadata]:
        raw = await self._client.get_eligible_types(profile_id, case_status)
        return [SRTypeMetadata(**item) for item in raw.get("types", [])]

    async def create_sr(self, sr_type: SRType, profile_id: str, user_id: str) -> SRDraftResponse:
        """Call Siebel to create SR, then create a local draft row.

        Raises ICMActiveSRConflictError if Siebel reports an active SR of the same type.
        """
        result = await self._client.create_sr(sr_type.value, profile_id)
        sr_id = result.get("sr_id", "")

        if self._draft_repo:
            await self._draft_repo.create(sr_id=sr_id, user_id=user_id, sr_type=sr_type.value)

        return SRDraftResponse(
            sr_id=sr_id,
            sr_type=sr_type,
            draft_json=None,
            updated_at=datetime.now(timezone.utc),
        )

    async def get_form_schema(self, sr_id: str, sr_type: SRType) -> Optional[DynamicFormSchema]:
        """Load form schema for an SR. Returns None for non-dynamic types."""
        if not SRTypeRegistry.is_dynamic(sr_type):
            return None

        # Stub schema — real implementation will load from DB/config per sr_type
        return DynamicFormSchema(
            form_type=DynamicFormType.SR,
            sr_type=sr_type,
            pages=[
                DynamicFormPage(
                    page_index=0,
                    title="Application Details",
                    fields=[
                        DynamicFormField(
                            field_id="reason",
                            label="Reason for Request",
                            field_type="textarea",
                            required=True,
                        ),
                    ],
                )
            ],
            total_pages=1,
        )

    async def save_form_draft(
        self, sr_id: str, answers: dict, page_index: int, user_id: str | None = None
    ) -> Optional[SRDraftResponse]:
        """Update draft_json for an existing sr_drafts row, optionally scoped to a specific user."""
        if not self._draft_repo:
            return None

        row = await self._draft_repo.update_form(
            sr_id=sr_id, answers=answers, page_index=page_index, user_id=user_id
        )
        if not row:
            return None

        draft_data = (
            row.draft_json
            if isinstance(row.draft_json, dict)
            else None
        )
        return SRDraftResponse(
            sr_id=row.sr_id,
            sr_type=SRType(row.sr_type),
            draft_json=draft_data,
            updated_at=row.updated_at,
        )

    async def submit_sr(
        self, sr_id: str, pin: str, spouse_pin: str | None, bceid_guid: str,
        user_id: str | None = None,
    ) -> SRSubmitResponse:
        """Submit an SR: validate PIN, generate PDF if needed, finalize in Siebel, delete draft."""
        from app.domains.service_requests.pdf_generation_service import PDFGenerationService

        from app.services.icm.exceptions import PINValidationError

        if not self._pin_service:
            raise RuntimeError("PINService not configured")
        await self._pin_service.validate_or_raise(bceid_guid, pin)

        if spouse_pin and not await self._pin_service.validate(bceid_guid, spouse_pin):
            raise PINValidationError("Invalid spouse PIN")

        # Get the draft to get answers for Siebel
        draft = await self.get_draft(sr_id, user_id=user_id)
        answers = draft.draft_json.get("answers", {}) if draft and draft.draft_json else {}
        sr_type = draft.sr_type if draft else None

        # Generate PDF if required for this SR type
        if sr_type and SRTypeRegistry.requires_pdf(sr_type):
            pdf_svc = PDFGenerationService()
            await pdf_svc.generate(sr_type.value, answers)

        # Finalize in Siebel
        result = await self._client.finalize_sr_form(sr_id, answers)
        sr_number = result.get("sr_number", "")

        # Delete the draft
        if self._draft_repo:
            await self._draft_repo.delete(sr_id=sr_id, user_id=user_id)

        return SRSubmitResponse(
            sr_id=sr_id,
            sr_number=sr_number,
            submitted_at=datetime.now(timezone.utc),
        )

    async def get_sr_detail(self, sr_id: str) -> Optional[SRDetailResponse]:
        raw = await self._client.get_sr_detail(sr_id)
        if not raw:
            return None
        return SRDetailResponse(**raw)

    async def withdraw_sr(self, sr_id: str, reason: str | None) -> None:
        await self._client.cancel_sr(sr_id, reason or "")

    async def get_draft(self, sr_id: str, user_id: str | None = None) -> Optional[SRDraftResponse]:
        """Retrieve a draft by sr_id, optionally scoped to a specific user."""
        if not self._draft_repo:
            return None

        row = await self._draft_repo.get(sr_id=sr_id, user_id=user_id)
        if not row:
            return None

        draft_data = (
            row.draft_json
            if isinstance(row.draft_json, dict)
            else None
        )
        return SRDraftResponse(
            sr_id=row.sr_id,
            sr_type=SRType(row.sr_type),
            draft_json=draft_data,
            updated_at=row.updated_at,
        )
