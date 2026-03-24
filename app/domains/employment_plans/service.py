from app.services.icm.employment_plans import SiebelEPClient
from app.domains.employment_plans.models import (
    EmploymentPlan, EPListResponse, EPDetailResponse, EPSignResponse,
)
from datetime import datetime, timezone


class EmploymentPlanService:
    def __init__(self, client: SiebelEPClient):
        self._client = client

    async def list_plans(self, profile_id: str) -> EPListResponse:
        data = await self._client.get_ep_list(profile_id)
        plans = [EmploymentPlan(**p) for p in data.get("plans", [])]
        # Sort by plan_date descending
        plans.sort(key=lambda p: p.plan_date, reverse=True)
        return EPListResponse(plans=plans)

    async def get_detail(self, ep_id: str) -> EPDetailResponse:
        data = await self._client.get_ep_detail(ep_id)
        return EPDetailResponse(**data)

    async def sign_and_send(self, ep_id: str, pin: str, message_id: int, profile_id: str) -> EPSignResponse:
        # Send to ICM first
        await self._client.send_to_icm(ep_id, pin)
        # Mark as submitted
        await self._client.mark_form_submitted(ep_id, message_id)
        return EPSignResponse(
            ep_id=int(ep_id),
            signed_at=datetime.now(timezone.utc),
        )
