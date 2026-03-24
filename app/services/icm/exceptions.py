class ICMError(Exception):
    """Base exception for all ICM integration errors."""
    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class ICMCaseNotFoundError(ICMError):
    """Raised when ICM reports no case for the given profile (ICM_ERR_NO_CASE)."""


class ICMAccessRevokedError(ICMError):
    """Raised when ICM reports access has been revoked (ICM_ERR_REVOKED)."""


class ICMContactNotFoundError(ICMError):
    """Raised when ICM reports no contact record exists (ICM_ERR_NO_CONTACT)."""


class ICMMultipleContactsError(ICMError):
    """Raised when ICM finds multiple matching contacts (ICM_ERR_MULTI_CONTACTS)."""


class ICMClosedCaseError(ICMError):
    """Raised when ICM reports the case is closed (ICM_ERR_CLOSED_CASE)."""


class ICMActiveSRConflictError(ICMError):
    """Raised when ICM reports an active SR of the same type already exists."""


class ICMSRAlreadyWithdrawnError(ICMError):
    """Raised when ICM reports the SR is already in a withdrawn state."""


class ICMServiceUnavailableError(ICMError):
    """Raised when the circuit breaker is open or ICM is unreachable."""


class PINValidationError(Exception):
    """Raised when PIN validation fails."""
