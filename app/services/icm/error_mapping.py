from app.services.icm.exceptions import (
    ICMError,
    ICMCaseNotFoundError,
    ICMAccessRevokedError,
    ICMContactNotFoundError,
    ICMMultipleContactsError,
    ICMClosedCaseError,
    ICMActiveSRConflictError,
    ICMSRAlreadyWithdrawnError,
)

_ERROR_MAP: dict[str, type[ICMError]] = {
    "ICM_ERR_NO_CASE": ICMCaseNotFoundError,
    "ICM_ERR_REVOKED": ICMAccessRevokedError,
    "ICM_ERR_NO_CONTACT": ICMContactNotFoundError,
    "ICM_ERR_MULTI_CONTACTS": ICMMultipleContactsError,
    "ICM_ERR_CLOSED_CASE": ICMClosedCaseError,
    "ICM_ERR_ACTIVE_SR_CONFLICT": ICMActiveSRConflictError,
    "ICM_ERR_SR_ALREADY_WITHDRAWN": ICMSRAlreadyWithdrawnError,
}


def map_icm_error(response_body: dict) -> ICMError:
    """Map an ICM error response body to a typed ICMError subclass."""
    error_code = response_body.get("errorCode", "")
    message = response_body.get("message", "ICM error")
    exc_class = _ERROR_MAP.get(error_code, ICMError)
    return exc_class(message, error_code=error_code)
