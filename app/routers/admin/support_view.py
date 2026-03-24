from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel

from app.cache.redis_client import get_redis
from app.dependencies.require_worker_role import require_worker_role
from app.dependencies.require_support_view_session import (
    require_support_view_session,
    set_session,
    delete_session,
)
from app.auth.models import UserContext
from app.models.admin import SupportViewSessionData
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.deps import get_siebel_admin_client

support_view_router = APIRouter(prefix="/admin/support-view", tags=["admin"])

SUPPORT_VIEW_TTL_MINUTES = 15


class TombstoneRequest(BaseModel):
    client_bceid_guid: str


class SearchRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    sin: str | None = None
    page: int = 1


def _get_admin_service() -> SiebelAdminClient:
    return get_siebel_admin_client()


@support_view_router.post("/search")
async def search_clients(
    body: SearchRequest,
    user: UserContext = Depends(require_worker_role),
    admin_client: SiebelAdminClient = Depends(_get_admin_service),
):
    """Search client profiles by name or SIN. Uses POST to avoid SIN in URL/logs."""
    result = await admin_client.search_profiles(
        first_name=body.first_name,
        last_name=body.last_name,
        sin=body.sin,
        page=body.page,
    )
    return result


@support_view_router.post("/tombstone")
async def create_tombstone(
    body: TombstoneRequest,
    user: UserContext = Depends(require_worker_role),
    admin_client: SiebelAdminClient = Depends(_get_admin_service),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Create a support view session for a client. Rejects self-impersonation."""
    # Self-impersonation check: workers authenticate via IDIR (user_id is IDIR GUID).
    # If the worker also has a BCeID (dual identity), compare against bceid_guid.
    if user.bceid_guid and body.client_bceid_guid == user.bceid_guid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-impersonation is not allowed",
        )

    profile = await admin_client.get_client_profile(body.client_bceid_guid)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=SUPPORT_VIEW_TTL_MINUTES)

    session = SupportViewSessionData(
        worker_idir=user.idir_username,
        client_portal_id=profile.get("portal_id", body.client_bceid_guid),
        client_bceid_guid=body.client_bceid_guid,
        activated_at=now,
        expires_at=expires_at,
    )

    key = f"{user.idir_username}:{body.client_bceid_guid}"
    await set_session(key, session, redis)

    return {
        "session_token": key,
        "client_bceid_guid": body.client_bceid_guid,
        "expires_at": expires_at.isoformat(),
    }


@support_view_router.delete("/tombstone", status_code=status.HTTP_204_NO_CONTENT)
async def end_tombstone(
    x_support_view_client: str = Header(
        ..., description="Client BCeID GUID to end session for"
    ),
    user: UserContext = Depends(require_worker_role),
    redis: aioredis.Redis = Depends(get_redis),
):
    """End (delete) an active support view session."""
    key = f"{user.idir_username}:{x_support_view_client}"
    await delete_session(key, redis)


@support_view_router.get("/client-data/{resource}")
async def get_client_data(
    resource: str,
    session: SupportViewSessionData = Depends(require_support_view_session),
):
    """Proxy endpoint for impersonated client data. Requires an active support view session."""
    return {
        "resource": resource,
        "client_bceid_guid": session.client_bceid_guid,
        "client_portal_id": session.client_portal_id,
        "data": {},
    }
