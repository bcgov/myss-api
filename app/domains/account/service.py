import structlog
from app.domains.account.models import AccountInfoResponse, UpdateContactRequest, CaseMemberListResponse

logger = structlog.get_logger()


class AccountService:
    def __init__(self, client):
        self._client = client

    async def get_profile(self, user_id: str) -> AccountInfoResponse:
        data = await self._client.get_profile(user_id)
        return AccountInfoResponse(**data)

    async def update_contact(self, user_id: str, request: UpdateContactRequest) -> None:
        await self._client.update_contact(user_id, request.model_dump())

    async def get_case_members(self, user_id: str) -> CaseMemberListResponse:
        data = await self._client.get_case_members(user_id)
        return CaseMemberListResponse(**data)

    async def post_login_sync(self, user_id: str) -> None:
        try:
            await self._client.sync_profile(user_id)
        except Exception:
            logger.warning("post_login_sync_failed", user_id=user_id, exc_info=True)
