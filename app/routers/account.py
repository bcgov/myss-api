from fastapi import APIRouter, BackgroundTasks, Depends

from app.auth.dependencies import require_role
from app.auth.models import UserContext, UserRole
from app.services.icm.deps import get_siebel_account_client
from app.domains.account.models import AccountInfoResponse, UpdateContactRequest, CaseMemberListResponse
from app.domains.account.service import AccountService

account_router = APIRouter(prefix="/account", tags=["account"])


def _get_account_service() -> AccountService:
    return AccountService(client=get_siebel_account_client())


@account_router.get("/profile", response_model=AccountInfoResponse)
async def get_profile(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AccountService = Depends(_get_account_service),
) -> AccountInfoResponse:
    return await svc.get_profile(user.user_id)


@account_router.patch("/contact", status_code=200)
async def update_contact(
    request: UpdateContactRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AccountService = Depends(_get_account_service),
):
    await svc.update_contact(user.user_id, request)
    return {"status": "ok"}


@account_router.get("/case-members", response_model=CaseMemberListResponse)
async def get_case_members(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AccountService = Depends(_get_account_service),
) -> CaseMemberListResponse:
    return await svc.get_case_members(user.user_id)


@account_router.post("/post-login-sync", status_code=202)
async def post_login_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: AccountService = Depends(_get_account_service),
):
    background_tasks.add_task(svc.post_login_sync, user.user_id)
    return {"status": "accepted"}
