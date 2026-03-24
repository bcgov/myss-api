import structlog
import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db.session import AsyncSessionLocal
from app.models.audit import WorkerAuditRecord

logger = structlog.get_logger(__name__)


async def _persist_audit_record(record: WorkerAuditRecord) -> None:
    """Persist audit record to the database. Best-effort — failures are logged."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(record)
            await session.commit()
    except Exception:
        logger.warning("audit_persist_failed", worker_idir=record.worker_idir, action=record.action, exc_info=True)


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that intercepts all /admin/ requests and writes audit records.

    Audit is best-effort — does NOT block the response if persistence fails.
    JWT is decoded but NOT validated here; validation happens in the dependency layer.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        path = request.url.path
        if not path.startswith("/admin/"):
            return response

        # Skip audit for auth failures — claims may be forged
        if response.status_code in (401, 403):
            return response

        # Extract worker info from JWT (decode only, no validation)
        worker_idir = "unknown"
        worker_role = "unknown"
        client_bceid_guid = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                payload = pyjwt.decode(token, options={"verify_signature": False})
                worker_idir = payload.get("idir_username") or payload.get("sub", "unknown")
                worker_role = payload.get("role", "unknown")
                client_bceid_guid = payload.get("bceid_guid")
            except Exception:
                pass  # JWT decode failed — still pass through

        # Extract resource_type and resource_id from path segments after /admin/
        path_parts = [p for p in path.split("/") if p]
        # path_parts[0] == "admin"
        resource_type = path_parts[1] if len(path_parts) > 1 else "unknown"
        resource_id = path_parts[3] if len(path_parts) > 3 else None

        action = f"{request.method} {path}"
        request_ip = request.client.host if request.client else "unknown"

        record = WorkerAuditRecord(
            worker_idir=worker_idir,
            worker_role=worker_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            client_bceid_guid=client_bceid_guid,
            request_ip=request_ip,
        )

        await _persist_audit_record(record)

        return response
