"""Mock ICM clients for local development without Siebel VPN access."""

from app.services.icm.account import SiebelAccountClient
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.attachments import SiebelAttachmentClient
from app.services.icm.employment_plans import SiebelEPClient
from app.services.icm.monthly_report import SiebelMonthlyReportClient
from app.services.icm.notifications import SiebelNotificationClient
from app.services.icm.payment import SiebelPaymentClient
from app.services.icm.profile import SiebelProfileClient
from app.services.icm.registration import SiebelRegistrationClient
from app.services.icm.service_requests import SiebelSRClient

from app.services.icm.mock.account import MockAccountClient
from app.services.icm.mock.admin import MockAdminClient
from app.services.icm.mock.attachments import MockAttachmentClient
from app.services.icm.mock.employment_plans import MockEPClient
from app.services.icm.mock.monthly_report import MockMonthlyReportClient
from app.services.icm.mock.notifications import MockNotificationClient
from app.services.icm.mock.payment import MockPaymentClient
from app.services.icm.mock.profile import MockProfileClient
from app.services.icm.mock.registration import MockRegistrationClient
from app.services.icm.mock.service_requests import MockSRClient

MOCK_CLIENT_MAP: dict[type, type] = {
    SiebelAccountClient: MockAccountClient,
    SiebelAdminClient: MockAdminClient,
    SiebelAttachmentClient: MockAttachmentClient,
    SiebelEPClient: MockEPClient,
    SiebelMonthlyReportClient: MockMonthlyReportClient,
    SiebelNotificationClient: MockNotificationClient,
    SiebelPaymentClient: MockPaymentClient,
    SiebelProfileClient: MockProfileClient,
    SiebelRegistrationClient: MockRegistrationClient,
    SiebelSRClient: MockSRClient,
}
