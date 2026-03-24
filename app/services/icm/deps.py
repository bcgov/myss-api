import os
from typing import TypeVar, Type
from app.services.icm.client import ICMClient

T = TypeVar("T", bound=ICMClient)

_clients: dict[type, ICMClient] = {}


def _icm_kwargs() -> dict:
    return {
        "base_url": os.environ["ICM_BASE_URL"],
        "client_id": os.environ["ICM_CLIENT_ID"],
        "client_secret": os.environ["ICM_CLIENT_SECRET"],
        "token_url": os.environ["ICM_TOKEN_URL"],
    }


def get_siebel_client(cls: Type[T]) -> T:
    if cls not in _clients:
        _clients[cls] = cls(**_icm_kwargs())
    return _clients[cls]  # type: ignore[return-value]


def clear_clients() -> None:
    """Clear the client cache. Call in test fixtures for isolation."""
    _clients.clear()


# Backward-compatible aliases (used by existing router imports)
def get_siebel_profile_client():
    from app.services.icm.profile import SiebelProfileClient
    return get_siebel_client(SiebelProfileClient)

def get_siebel_registration_client():
    from app.services.icm.registration import SiebelRegistrationClient
    return get_siebel_client(SiebelRegistrationClient)

def get_siebel_sr_client():
    from app.services.icm.service_requests import SiebelSRClient
    return get_siebel_client(SiebelSRClient)

def get_siebel_monthly_report_client():
    from app.services.icm.monthly_report import SiebelMonthlyReportClient
    return get_siebel_client(SiebelMonthlyReportClient)

def get_siebel_notification_client():
    from app.services.icm.notifications import SiebelNotificationClient
    return get_siebel_client(SiebelNotificationClient)

def get_siebel_payment_client():
    from app.services.icm.payment import SiebelPaymentClient
    return get_siebel_client(SiebelPaymentClient)

def get_siebel_ep_client():
    from app.services.icm.employment_plans import SiebelEPClient
    return get_siebel_client(SiebelEPClient)

def get_siebel_attachment_client():
    from app.services.icm.attachments import SiebelAttachmentClient
    return get_siebel_client(SiebelAttachmentClient)

def get_siebel_admin_client():
    from app.services.icm.admin import SiebelAdminClient
    return get_siebel_client(SiebelAdminClient)

def get_siebel_account_client():
    from app.services.icm.account import SiebelAccountClient
    return get_siebel_client(SiebelAccountClient)
