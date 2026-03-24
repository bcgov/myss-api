from uuid import UUID

# TTL constants (seconds)
SESSION_TTL: int = 900           # 15 minutes — matches session timeout
ICM_CASE_TTL: int = 300          # 5 minutes — case status cache
ICM_PAYMENT_TTL: int = 3600      # 1 hour — payment details cache
ICM_CHEQUE_SCHEDULE_TTL: int = 3600  # 1 hour — shared by D3 and D5
ICM_BANNERS_TTL: int = 300       # 5 minutes — banner notifications
SUPPORT_VIEW_TTL: int = 900      # 15 minutes — worker support view session
PIN_RESET_TTL: int = 3600        # 1 hour — PIN reset attempt rate limiting


def session_key(user_id: UUID) -> str:
    """Redis key for Auth.js session data."""
    return f"session:{user_id}"


def icm_case_key(case_number: str) -> str:
    """Redis key for ICM case status cache (TTL: 5 minutes)."""
    return f"icm_cache:case:{case_number}"


def icm_payment_key(case_number: str) -> str:
    """Redis key for ICM payment info cache (TTL: 1 hour)."""
    return f"icm_cache:payment:{case_number}"


def icm_cheque_schedule_key(case_number: str) -> str:
    """Redis key for cheque schedule cache — shared by D3 and D5 (TTL: 1 hour)."""
    return f"icm_cache:cheque_schedule:{case_number}"


def icm_banners_key(case_number: str) -> str:
    """Redis key for banner notification cache (TTL: 5 minutes)."""
    return f"icm_cache:banners:{case_number}"


def support_view_key(worker_idir: str) -> str:
    """Redis key for worker support view session (TTL: 15 minutes)."""
    return f"support_view:{worker_idir}"


def pin_reset_key(profile_id: UUID) -> str:
    """Redis key for PIN reset attempt rate limiting (TTL: 1 hour)."""
    return f"pin_reset:{profile_id}"
