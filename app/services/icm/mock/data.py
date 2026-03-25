"""
Canned response data for mock ICM clients.

Organized by domain, keyed by persona identifiers (bceid_guid, profile_id,
case_number) so mock clients can look up the correct persona's data.

Three personas:
  Alice Thompson — single client, active case, 1 dependant
  Bob Chen — couple with spouse Maria, PWD designation, active case
  Carol Williams — closed case, unlinked profile, edge-case testing
"""

from datetime import datetime, date, timedelta, UTC
from uuid import uuid4

# ---------------------------------------------------------------------------
# Persona constants
# ---------------------------------------------------------------------------

ALICE_USER_ID = "a0000000-0000-0000-0000-000000000001"
BOB_USER_ID = "b0000000-0000-0000-0000-000000000002"
CAROL_USER_ID = "c0000000-0000-0000-0000-000000000003"

ALICE_BCEID = "alice-bceid-1001"
BOB_BCEID = "bob-bceid-1002"
CAROL_BCEID = "carol-bceid-1003"

ALICE_PROFILE_ID = "a1000000-0000-0000-0000-000000000001"
BOB_PROFILE_ID = "b1000000-0000-0000-0000-000000000002"
CAROL_PROFILE_ID = "c1000000-0000-0000-0000-000000000003"

ALICE_PORTAL_ID = "PTL-ALICE-001"
BOB_PORTAL_ID = "PTL-BOB-002"
CAROL_PORTAL_ID = "PTL-CAROL-003"

ALICE_MIS_ID = "MIS-001"
BOB_MIS_ID = "MIS-002"
CAROL_MIS_ID = "MIS-003"

ALICE_CASE = "100100"
BOB_CASE = "100200"
CAROL_CASE = "100300"

WORKER_IDIR = "jsmith"

# Map bceid_guid → persona data for lookups
_BCEID_TO_PROFILE_ID = {
    ALICE_BCEID: ALICE_PROFILE_ID,
    BOB_BCEID: BOB_PROFILE_ID,
    CAROL_BCEID: CAROL_PROFILE_ID,
}

_BCEID_TO_CASE = {
    ALICE_BCEID: ALICE_CASE,
    BOB_BCEID: BOB_CASE,
    CAROL_BCEID: CAROL_CASE,
}

_PROFILE_TO_CASE = {
    ALICE_PROFILE_ID: ALICE_CASE,
    BOB_PROFILE_ID: BOB_CASE,
    CAROL_PROFILE_ID: CAROL_CASE,
}

_CASE_TO_PROFILE = {v: k for k, v in _PROFILE_TO_CASE.items()}

# Default persona for unknown IDs
_DEFAULT_PROFILE_ID = ALICE_PROFILE_ID
_DEFAULT_CASE = ALICE_CASE

# Minimal valid PDF placeholder for byte-returning methods
MOCK_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
)

# Base64-encoded version for dict-returning methods (e.g. get_t5007_pdf)
import base64
MOCK_PDF_BASE64 = base64.b64encode(MOCK_PDF_BYTES).decode()


# ---------------------------------------------------------------------------
# Helper: compute relative dates from "now" so data stays fresh
# ---------------------------------------------------------------------------

def _today() -> date:
    return datetime.now(UTC).date()


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Account responses (SiebelAccountClient)
# ---------------------------------------------------------------------------

ACCOUNT_PROFILES = {
    ALICE_USER_ID: {
        "user_id": ALICE_USER_ID,
        "email": "alice.thompson@example.com",
        "phone_numbers": [
            {"phone_id": "PH-A1", "phone_number": "604-555-0101", "phone_type": "CELL"}
        ],
        "case_number": ALICE_CASE,
        "case_status": "Active",
        "first_name": "Alice",
        "last_name": "Thompson",
    },
    BOB_USER_ID: {
        "user_id": BOB_USER_ID,
        "email": "bob.chen@example.com",
        "phone_numbers": [
            {"phone_id": "PH-B1", "phone_number": "778-555-0202", "phone_type": "HOME"},
            {"phone_id": "PH-B2", "phone_number": "604-555-0203", "phone_type": "CELL"},
        ],
        "case_number": BOB_CASE,
        "case_status": "Active",
        "first_name": "Bob",
        "last_name": "Chen",
    },
    CAROL_USER_ID: {
        "user_id": CAROL_USER_ID,
        "email": "carol.williams@example.com",
        "phone_numbers": [
            {"phone_id": "PH-C1", "phone_number": "250-555-0303", "phone_type": "HOME"}
        ],
        "case_number": CAROL_CASE,
        "case_status": "Closed",
        "first_name": "Carol",
        "last_name": "Williams",
    },
}

CASE_MEMBERS = {
    ALICE_USER_ID: {
        "members": [
            {"name": "Lily Thompson", "relationship": "Child"},
        ]
    },
    BOB_USER_ID: {
        "members": [
            {"name": "Maria Chen", "relationship": "Spouse"},
            {"name": "Emily Chen", "relationship": "Child"},
            {"name": "James Chen", "relationship": "Child"},
        ]
    },
    CAROL_USER_ID: {"members": []},
}


# ---------------------------------------------------------------------------
# Profile / tombstone responses (SiebelProfileClient)
# ---------------------------------------------------------------------------

TOMBSTONES = {
    ALICE_BCEID: {
        "bceid_guid": ALICE_BCEID,
        "first_name": "Alice",
        "last_name": "Thompson",
        "date_of_birth": "1990-03-15",
        "gender": "F",
        "email": "alice.thompson@example.com",
        "phone_number": "604-555-0101",
        "phone_type": "CELL",
        "address": {
            "street": "123 Main St",
            "city": "Vancouver",
            "province": "BC",
            "postal_code": "V5K 0A1",
        },
        "case_number": ALICE_CASE,
        "case_status": "Active",
    },
    BOB_BCEID: {
        "bceid_guid": BOB_BCEID,
        "first_name": "Bob",
        "last_name": "Chen",
        "date_of_birth": "1985-07-22",
        "gender": "M",
        "email": "bob.chen@example.com",
        "phone_number": "778-555-0202",
        "phone_type": "HOME",
        "address": {
            "street": "456 Oak Ave",
            "city": "Surrey",
            "province": "BC",
            "postal_code": "V3T 1Z4",
        },
        "case_number": BOB_CASE,
        "case_status": "Active",
    },
    CAROL_BCEID: {
        "bceid_guid": CAROL_BCEID,
        "first_name": "Carol",
        "last_name": "Williams",
        "date_of_birth": "1978-11-02",
        "gender": "F",
        "email": "carol.williams@example.com",
        "phone_number": "250-555-0303",
        "phone_type": "HOME",
        "address": {
            "street": "789 Cedar Rd",
            "city": "Victoria",
            "province": "BC",
            "postal_code": "V8W 2C3",
        },
        "case_number": CAROL_CASE,
        "case_status": "Closed",
    },
}

PROFILE_DATA = {
    ALICE_BCEID: {
        "bceid_guid": ALICE_BCEID,
        "portal_id": ALICE_PORTAL_ID,
        "profile_id": ALICE_PROFILE_ID,
        "link_code": "LINKED",
        "case_number": ALICE_CASE,
        "case_status": "Active",
    },
    BOB_BCEID: {
        "bceid_guid": BOB_BCEID,
        "portal_id": BOB_PORTAL_ID,
        "profile_id": BOB_PROFILE_ID,
        "link_code": "LINKED",
        "case_number": BOB_CASE,
        "case_status": "Active",
    },
    CAROL_BCEID: {
        "bceid_guid": CAROL_BCEID,
        "portal_id": CAROL_PORTAL_ID,
        "profile_id": CAROL_PROFILE_ID,
        "link_code": "UNLINKED",
        "case_number": CAROL_CASE,
        "case_status": "Closed",
    },
}


# ---------------------------------------------------------------------------
# Payment responses (SiebelPaymentClient)
# ---------------------------------------------------------------------------

def _cheque_schedule(case_number: str) -> dict:
    """Generate 3 months of cheque schedule from today."""
    today = _today()
    months = []
    for i in range(3):
        benefit_month = today.replace(day=1) + timedelta(days=32 * i)
        benefit_month = benefit_month.replace(day=1)
        months.append({
            "benefit_month": benefit_month.isoformat(),
            "income_date": (benefit_month - timedelta(days=10)).isoformat(),
            "cheque_issue_date": (benefit_month + timedelta(days=20)).isoformat(),
            "period_close_date": (benefit_month + timedelta(days=15)).isoformat(),
        })
    return {"schedule": months}


PAYMENT_INFO = {
    ALICE_CASE: {
        "upcoming_benefit_date": None,  # filled dynamically
        "assistance_type": "EA",
        "supplements": [
            {"code": 32, "amount": "50.00", "effective_date": "2025-01-01"},
        ],
        "service_provider_payments": [],
        "mis_data": {
            "mis_person_id": ALICE_MIS_ID,
            "key_player_name": "Alice Thompson",
            "spouse_name": None,
            "payment_method": "Direct Deposit",
            "payment_distribution": "Single",
            "allowances": [
                {"code": 41, "amount": "760.00", "description": "Support"},
                {"code": 42, "amount": "500.00", "description": "Shelter"},
                {"code": 32, "amount": "50.00", "description": "Housing Stability Supplement"},
            ],
            "deductions": [
                {"code": 99, "amount": "50.00", "description": "Earned Income Exemption"},
            ],
            "aee_balance": "200.00",
        },
    },
    BOB_CASE: {
        "upcoming_benefit_date": None,
        "assistance_type": "EA",
        "supplements": [
            {"code": 32, "amount": "75.00", "effective_date": "2025-01-01"},
            {"code": 73, "amount": "45.00", "effective_date": "2025-06-01"},
        ],
        "service_provider_payments": [
            {"provider_name": "BC Hydro", "amount": "120.00", "payment_date": None},
        ],
        "mis_data": {
            "mis_person_id": BOB_MIS_ID,
            "key_player_name": "Bob Chen",
            "spouse_name": "Maria Chen",
            "payment_method": "Direct Deposit",
            "payment_distribution": "Couple",
            "allowances": [
                {"code": 41, "amount": "1120.00", "description": "Support"},
                {"code": 42, "amount": "750.00", "description": "Shelter"},
                {"code": 32, "amount": "75.00", "description": "Housing Stability Supplement"},
                {"code": 73, "amount": "45.00", "description": "Hardship/Comforts"},
            ],
            "deductions": [],
            "aee_balance": "0.00",
        },
    },
    CAROL_CASE: {
        "upcoming_benefit_date": None,
        "assistance_type": "EA",
        "supplements": [],
        "service_provider_payments": [],
        "mis_data": {
            "mis_person_id": CAROL_MIS_ID,
            "key_player_name": "Carol Williams",
            "spouse_name": None,
            "payment_method": "Cheque",
            "payment_distribution": "Single",
            "allowances": [],
            "deductions": [],
            "aee_balance": "0.00",
        },
    },
}

T5007_SLIPS = {
    ALICE_PROFILE_ID: {
        "slips": [
            {"tax_year": 2025, "box_10_amount": "15720.00", "box_11_amount": "0.00", "available": True},
            {"tax_year": 2024, "box_10_amount": "14880.00", "box_11_amount": "0.00", "available": True},
        ]
    },
    BOB_PROFILE_ID: {
        "slips": [
            {"tax_year": 2025, "box_10_amount": "23280.00", "box_11_amount": "540.00", "available": True},
            {"tax_year": 2024, "box_10_amount": "22100.00", "box_11_amount": "540.00", "available": True},
        ]
    },
    CAROL_PROFILE_ID: {"slips": []},
}

T5_HISTORY_YEARS = {
    ALICE_PROFILE_ID: {"years": [2025, 2024]},
    BOB_PROFILE_ID: {"years": [2025, 2024]},
    CAROL_PROFILE_ID: {"years": []},
}

MIS_DATA = {
    ALICE_PROFILE_ID: PAYMENT_INFO[ALICE_CASE]["mis_data"],
    BOB_PROFILE_ID: PAYMENT_INFO[BOB_CASE]["mis_data"],
    CAROL_PROFILE_ID: PAYMENT_INFO[CAROL_CASE]["mis_data"],
}


# ---------------------------------------------------------------------------
# Notification responses (SiebelNotificationClient)
# ---------------------------------------------------------------------------

BANNERS = {
    ALICE_CASE: {
        "banners": [
            {
                "notification_id": "BNR-001",
                "body": "Scheduled maintenance: March 29, 10PM-2AM. Some services may be unavailable.",
                "start_date": "2026-03-25",
                "end_date": "2026-03-30",
            },
            {
                "notification_id": "BNR-002",
                "body": "New: You can now view T5007 tax slips online for 2025.",
                "start_date": "2026-02-01",
                "end_date": "2026-04-30",
            },
        ]
    },
    BOB_CASE: {
        "banners": [
            {
                "notification_id": "BNR-001",
                "body": "Scheduled maintenance: March 29, 10PM-2AM. Some services may be unavailable.",
                "start_date": "2026-03-25",
                "end_date": "2026-03-30",
            },
        ]
    },
    CAROL_CASE: {"banners": []},
}

MESSAGES = {
    ALICE_PROFILE_ID: {
        "messages": [
            {
                "message_id": "MSG-A001",
                "subject": "Monthly Report Reminder",
                "sent_date": "2026-03-15T09:00:00Z",
                "is_read": False,
                "can_reply": False,
                "message_type": "SD81_STANDARD",
            },
            {
                "message_id": "MSG-A002",
                "subject": "Service Request Received",
                "sent_date": "2026-03-10T14:30:00Z",
                "is_read": True,
                "can_reply": False,
                "message_type": "FORM_SUBMISSION",
            },
            {
                "message_id": "MSG-A003",
                "subject": "Important Update About Your Benefits",
                "sent_date": "2026-03-01T10:00:00Z",
                "is_read": True,
                "can_reply": True,
                "message_type": "GENERAL",
            },
        ],
        "total": 3,
    },
    BOB_PROFILE_ID: {
        "messages": [
            {
                "message_id": "MSG-B001",
                "subject": "Monthly Report Restart Required",
                "sent_date": "2026-03-18T11:00:00Z",
                "is_read": False,
                "can_reply": False,
                "message_type": "SD81_RESTART",
            },
            {
                "message_id": "MSG-B002",
                "subject": "Employment Plan Ready for Signature",
                "sent_date": "2026-03-05T08:00:00Z",
                "is_read": True,
                "can_reply": False,
                "message_type": "GENERAL",
            },
        ],
        "total": 2,
    },
    CAROL_PROFILE_ID: {"messages": [], "total": 0},
}

MESSAGE_DETAILS = {
    "MSG-A001": {
        "message_id": "MSG-A001",
        "subject": "Monthly Report Reminder",
        "sent_date": "2026-03-15T09:00:00Z",
        "is_read": False,
        "can_reply": False,
        "message_type": "SD81_STANDARD",
        "body": "Your monthly report for March 2026 is due. Please submit it before the period close date to avoid delays in your benefit payment.",
        "attachments": [],
    },
    "MSG-A002": {
        "message_id": "MSG-A002",
        "subject": "Service Request Received",
        "sent_date": "2026-03-10T14:30:00Z",
        "is_read": True,
        "can_reply": False,
        "message_type": "FORM_SUBMISSION",
        "body": "We have received your service request SR-100101. You will be notified when it has been reviewed.",
        "attachments": [],
    },
    "MSG-A003": {
        "message_id": "MSG-A003",
        "subject": "Important Update About Your Benefits",
        "sent_date": "2026-03-01T10:00:00Z",
        "is_read": True,
        "can_reply": True,
        "message_type": "GENERAL",
        "body": "Effective April 1, 2026, shelter allowance rates have been updated. Please review your payment information for details.",
        "attachments": [],
    },
    "MSG-B001": {
        "message_id": "MSG-B001",
        "subject": "Monthly Report Restart Required",
        "sent_date": "2026-03-18T11:00:00Z",
        "is_read": False,
        "can_reply": False,
        "message_type": "SD81_RESTART",
        "body": "Your monthly report for March 2026 requires additional information. Please restart and resubmit.",
        "attachments": [],
    },
    "MSG-B002": {
        "message_id": "MSG-B002",
        "subject": "Employment Plan Ready for Signature",
        "sent_date": "2026-03-05T08:00:00Z",
        "is_read": True,
        "can_reply": False,
        "message_type": "GENERAL",
        "body": "Your employment plan EP-B001 is ready for your electronic signature. Please review and sign at your earliest convenience.",
        "attachments": [{"attachment_id": "ATT-EP-001", "filename": "employment_plan_2026.pdf"}],
    },
}


# ---------------------------------------------------------------------------
# Service Request responses (SiebelSRClient)
# ---------------------------------------------------------------------------

SR_LISTS = {
    ALICE_PROFILE_ID: {
        "items": [
            {
                "sr_id": "SR-A001",
                "sr_type": "ASSIST",
                "sr_number": "SR-100101",
                "status": "Open",
                "client_name": "Alice Thompson",
                "created_at": "2026-03-10T14:30:00Z",
            },
            {
                "sr_id": "SR-A002",
                "sr_type": "CRISIS_FOOD",
                "sr_number": "SR-100102",
                "status": "Submitted",
                "client_name": "Alice Thompson",
                "created_at": "2026-02-15T09:00:00Z",
            },
        ],
        "total": 2,
        "page": 1,
        "page_size": 10,
    },
    BOB_PROFILE_ID: {
        "items": [
            {
                "sr_id": "SR-B001",
                "sr_type": "DIRECT_DEPOSIT",
                "sr_number": "SR-100201",
                "status": "Cancelled",
                "client_name": "Bob Chen",
                "created_at": "2026-01-20T11:00:00Z",
            },
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
    },
    CAROL_PROFILE_ID: {"items": [], "total": 0, "page": 1, "page_size": 10},
}

SR_DETAILS = {
    "SR-A001": {
        "sr_id": "SR-A001",
        "sr_type": "ASSIST",
        "sr_number": "SR-100101",
        "status": "Open",
        "client_name": "Alice Thompson",
        "created_at": "2026-03-10T14:30:00Z",
        "answers": {"employment_status": "unemployed", "seeking_employment": True},
        "attachments": [],
    },
    "SR-A002": {
        "sr_id": "SR-A002",
        "sr_type": "CRISIS_FOOD",
        "sr_number": "SR-100102",
        "status": "Submitted",
        "client_name": "Alice Thompson",
        "created_at": "2026-02-15T09:00:00Z",
        "answers": {"crisis_type": "food", "amount_requested": "200.00"},
        "attachments": [],
    },
    "SR-B001": {
        "sr_id": "SR-B001",
        "sr_type": "DIRECT_DEPOSIT",
        "sr_number": "SR-100201",
        "status": "Cancelled",
        "client_name": "Bob Chen",
        "created_at": "2026-01-20T11:00:00Z",
        "answers": {"bank_name": "TD Canada Trust", "transit_number": "00123", "account_number": "1234567"},
        "attachments": [],
    },
}

ELIGIBLE_SR_TYPES = {
    "Active": {
        "types": [
            {"sr_type": "ASSIST", "display_name": "Income Assistance", "requires_pin": True, "has_attachments": False, "max_active": 1},
            {"sr_type": "CRISIS_FOOD", "display_name": "Crisis - Food", "requires_pin": True, "has_attachments": False, "max_active": 1},
            {"sr_type": "CRISIS_SHELTER", "display_name": "Crisis - Shelter", "requires_pin": True, "has_attachments": True, "max_active": 1},
            {"sr_type": "DIRECT_DEPOSIT", "display_name": "Direct Deposit Change", "requires_pin": True, "has_attachments": True, "max_active": 1},
            {"sr_type": "DIET", "display_name": "Diet Supplement", "requires_pin": True, "has_attachments": True, "max_active": 1},
            {"sr_type": "BUS_PASS", "display_name": "Bus Pass", "requires_pin": True, "has_attachments": False, "max_active": 1},
        ]
    },
    "Closed": {"types": []},
}

SR_RETURN_ACTIONS = {
    "ASSIST": {"sr_type": "ASSIST", "action": "submit", "requires_pin": True},
    "CRISIS_FOOD": {"sr_type": "CRISIS_FOOD", "action": "submit", "requires_pin": True},
    "DIRECT_DEPOSIT": {"sr_type": "DIRECT_DEPOSIT", "action": "submit", "requires_pin": True},
}


# ---------------------------------------------------------------------------
# Monthly Report responses (SiebelMonthlyReportClient)
# ---------------------------------------------------------------------------

def _report_period(case_number: str) -> dict:
    today = _today()
    first_of_month = today.replace(day=1)
    return {
        "benefit_month": first_of_month.isoformat(),
        "income_date": (first_of_month - timedelta(days=10)).isoformat(),
        "cheque_issue_date": (first_of_month + timedelta(days=20)).isoformat(),
        "period_close_date": (first_of_month + timedelta(days=15)).isoformat(),
    }


MONTHLY_REPORTS = {
    ALICE_PROFILE_ID: {
        "reports": [
            {"sd81_id": "SD81-A001", "benefit_month": "2026-03-01", "status": "PRT", "submitted_at": None},
            {"sd81_id": "SD81-A002", "benefit_month": "2026-02-01", "status": "SUB", "submitted_at": "2026-02-14T16:00:00Z"},
            {"sd81_id": "SD81-A003", "benefit_month": "2026-01-01", "status": "RES", "submitted_at": "2026-01-18T10:00:00Z"},
        ],
        "total": 3,
    },
    BOB_PROFILE_ID: {
        "reports": [
            {"sd81_id": "SD81-B001", "benefit_month": "2026-03-01", "status": "PRT", "submitted_at": None},
            {"sd81_id": "SD81-B002", "benefit_month": "2026-02-01", "status": "SUB", "submitted_at": "2026-02-12T14:00:00Z"},
        ],
        "total": 2,
    },
    CAROL_PROFILE_ID: {"reports": [], "total": 0},
}

QUESTIONNAIRE = {
    "questions": [
        {"field_id": "income_amount", "label": "Total income this month", "field_type": "currency", "required": True},
        {"field_id": "income_source", "label": "Source of income", "field_type": "text", "required": False},
        {"field_id": "housing_change", "label": "Has your housing situation changed?", "field_type": "boolean", "required": True},
        {"field_id": "employment_change", "label": "Has your employment changed?", "field_type": "boolean", "required": True},
    ]
}

REPORT_SUMMARY = {
    "SD81-A001": {"sd81_id": "SD81-A001", "benefit_month": "2026-03-01", "status": "PRT", "answers": {}},
    "SD81-A002": {"sd81_id": "SD81-A002", "benefit_month": "2026-02-01", "status": "SUB", "answers": {"income_amount": "800.00", "housing_change": False}},
}


# ---------------------------------------------------------------------------
# Employment Plan responses (SiebelEPClient)
# ---------------------------------------------------------------------------

EP_LISTS = {
    ALICE_PROFILE_ID: {"plans": []},
    BOB_PROFILE_ID: {
        "plans": [
            {
                "ep_id": "EP-B001",
                "message_id": "MSG-B002",
                "icm_attachment_id": "ATT-EP-001",
                "status": "PENDING_SIGNATURE",
                "plan_date": "2026-03-01",
                "message_deleted": False,
            },
            {
                "ep_id": "EP-B002",
                "message_id": "MSG-B003",
                "icm_attachment_id": "ATT-EP-002",
                "status": "SUBMITTED",
                "plan_date": "2025-09-15",
                "message_deleted": False,
            },
        ]
    },
    CAROL_PROFILE_ID: {"plans": []},
}

EP_DETAILS = {
    "EP-B001": {
        "ep_id": "EP-B001",
        "message_id": "MSG-B002",
        "icm_attachment_id": "ATT-EP-001",
        "status": "PENDING_SIGNATURE",
        "plan_date": "2026-03-01",
        "message_deleted": False,
    },
    "EP-B002": {
        "ep_id": "EP-B002",
        "message_id": "MSG-B003",
        "icm_attachment_id": "ATT-EP-002",
        "status": "SUBMITTED",
        "plan_date": "2025-09-15",
        "message_deleted": False,
    },
}


# ---------------------------------------------------------------------------
# Registration responses (SiebelRegistrationClient)
# ---------------------------------------------------------------------------

REGISTRATION_RESPONSES = {
    "new": {
        "status": "success",
        "sr_number": "SR-REG-001",
        "message": "Registration submitted successfully",
    },
    "existing": {
        "status": "success",
        "portal_id": ALICE_PORTAL_ID,
        "profile_id": ALICE_PROFILE_ID,
        "message": "Profile linked successfully",
    },
}

LINK_OPTIONS = {
    ALICE_BCEID: {"options": ["portal_link"]},
    BOB_BCEID: {"options": ["portal_link"]},
    CAROL_BCEID: {"options": []},
}


# ---------------------------------------------------------------------------
# Admin responses (SiebelAdminClient)
# ---------------------------------------------------------------------------

ADMIN_SEARCH_RESULTS = {
    "results": [
        {
            "portal_id": ALICE_PORTAL_ID,
            "bceid_guid": ALICE_BCEID,
            "case_number": ALICE_CASE,
            "case_status": "Active",
            "full_name": "Alice Thompson",
        },
        {
            "portal_id": BOB_PORTAL_ID,
            "bceid_guid": BOB_BCEID,
            "case_number": BOB_CASE,
            "case_status": "Active",
            "full_name": "Bob Chen",
        },
    ],
    "total": 2,
    "page": 1,
    "page_size": 10,
}

ADMIN_CLIENT_PROFILES = {
    ALICE_BCEID: {
        "portal_id": ALICE_PORTAL_ID,
        "bceid_guid": ALICE_BCEID,
        "case_number": ALICE_CASE,
        "case_status": "Active",
        "full_name": "Alice Thompson",
        "contact_id": "CON-A001",
        "link_code": "LINKED",
        "last_login": "2026-03-20T10:00:00Z",
        "active_srs": [{"sr_number": "SR-100101", "sr_type": "ASSIST", "status": "Open"}],
    },
    BOB_BCEID: {
        "portal_id": BOB_PORTAL_ID,
        "bceid_guid": BOB_BCEID,
        "case_number": BOB_CASE,
        "case_status": "Active",
        "full_name": "Bob Chen",
        "contact_id": "CON-B001",
        "link_code": "LINKED",
        "last_login": "2026-03-19T14:30:00Z",
        "active_srs": [],
    },
    CAROL_BCEID: {
        "portal_id": CAROL_PORTAL_ID,
        "bceid_guid": CAROL_BCEID,
        "case_number": CAROL_CASE,
        "case_status": "Closed",
        "full_name": "Carol Williams",
        "contact_id": "CON-C001",
        "link_code": "UNLINKED",
        "last_login": "2026-01-15T08:00:00Z",
        "active_srs": [],
    },
}

WORKER_PERMISSIONS = {
    WORKER_IDIR: {
        "idir_username": WORKER_IDIR,
        "permissions": ["view_clients", "search_clients", "view_srs", "manage_ao_registration"],
    }
}


# ---------------------------------------------------------------------------
# Attachment responses (SiebelAttachmentClient)
# ---------------------------------------------------------------------------

ATTACHMENT_METADATA = {
    "ATT-001": {
        "attachment_id": "ATT-001",
        "filename": "proof_of_income.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 45000,
        "uploaded_at": "2026-03-10T14:35:00Z",
    },
    "ATT-002": {
        "attachment_id": "ATT-002",
        "filename": "bank_statement.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 128000,
        "uploaded_at": "2026-01-20T11:05:00Z",
    },
}
