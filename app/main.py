import logging
import os
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers.health import router as health_router
from app.routers.eligibility import router as eligibility_router
from app.routers.registration import router as registration_router
from app.routers.service_requests import router as sr_router
from app.routers.monthly_reports import router as mr_router
from app.routers.notifications import notifications_router, messages_router
from app.routers.payment import payment_router
from app.routers.employment_plans import ep_router
from app.routers.account import account_router
from app.routers.pin import pin_router
from app.routers.attachments import attachment_router
from app.routers.admin.support_view import support_view_router
from app.routers.admin.ao import ao_router
from app.middleware.audit_middleware import AuditMiddleware
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import UserContext, UserRole

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.auth.dependencies import validate_jwt_config
    validate_jwt_config()
    # Startup: nothing to initialize (connections are lazy)
    yield
    # Shutdown: close Redis pool and dispose SQLAlchemy engine
    from app.cache.redis_client import _redis_pool
    from app.db.session import engine
    from app.services.icm.deps import _clients, clear_clients
    if _redis_pool is not None:
        await _redis_pool.aclose()
    await engine.dispose()
    for client in _clients.values():
        try:
            await client.aclose()
        except Exception:
            pass
    clear_clients()


app = FastAPI(
    title="MySelfServe API",
    version="0.1.0",
    description="BC Government Income Assistance Self-Service Portal API",
    lifespan=lifespan,
)

_raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(eligibility_router)
app.include_router(registration_router)
app.include_router(sr_router)
app.include_router(mr_router)
app.include_router(notifications_router)
app.include_router(messages_router)
app.include_router(payment_router)
app.include_router(ep_router)
app.include_router(account_router)
app.include_router(pin_router)
app.include_router(attachment_router)
app.include_router(support_view_router)
app.include_router(ao_router)
app.add_middleware(AuditMiddleware)

# Global exception handlers — eliminate duplicated try/except blocks in routers
from app.exception_handlers import (
    icm_unavailable_handler,
    icm_conflict_handler,
    icm_sr_withdrawn_handler,
    pin_validation_handler,
    icm_error_handler,
)
from app.services.icm.exceptions import (
    ICMServiceUnavailableError,
    ICMActiveSRConflictError,
    ICMSRAlreadyWithdrawnError,
    PINValidationError,
    ICMError,
)

app.add_exception_handler(ICMServiceUnavailableError, icm_unavailable_handler)
app.add_exception_handler(ICMActiveSRConflictError, icm_conflict_handler)
app.add_exception_handler(ICMSRAlreadyWithdrawnError, icm_sr_withdrawn_handler)
app.add_exception_handler(PINValidationError, pin_validation_handler)
app.add_exception_handler(ICMError, icm_error_handler)
