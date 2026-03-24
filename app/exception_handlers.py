"""Global FastAPI exception handlers for ICM and PIN errors.

Eliminates duplicated try/except blocks across all routers.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.icm.exceptions import (
    ICMServiceUnavailableError,
    ICMActiveSRConflictError,
    ICMSRAlreadyWithdrawnError,
    PINValidationError,
)


async def icm_unavailable_handler(request: Request, exc: ICMServiceUnavailableError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable. Please try again later."},
    )


async def icm_conflict_handler(request: Request, exc: ICMActiveSRConflictError):
    return JSONResponse(
        status_code=409,
        content={"detail": "An active service request of this type already exists"},
    )


async def icm_sr_withdrawn_handler(request: Request, exc: ICMSRAlreadyWithdrawnError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Service request already withdrawn"},
    )


async def pin_validation_handler(request: Request, exc: PINValidationError):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)},
    )
