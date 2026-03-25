# Seed Data & Mock ICM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give developers a fully functional local environment without VPN access to Siebel/ICM — seed the database with realistic test data and auto-activate mock ICM clients in local mode.

**Architecture:** A standalone `scripts/seed_db.py` seeds all DB tables with 3 coherent test personas. Mock ICM client subclasses in `app/services/icm/mock/` override every real client method to return canned data. The existing `get_siebel_client()` factory in `deps.py` transparently swaps in mocks when `ENVIRONMENT=local` and `ICM_BASE_URL` is empty.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, SQLAlchemy async, PyJWT, bcrypt

**Spec:** `docs/superpowers/specs/2026-03-24-seed-data-and-mock-icm-design.md`

---

## File Map

### New files

| File | Purpose |
|---|---|
| `app/services/icm/mock/__init__.py` | Exports `MOCK_CLIENT_MAP` dict mapping real→mock classes |
| `app/services/icm/mock/data.py` | All canned response data, organized by domain and keyed by persona |
| `app/services/icm/mock/account.py` | `MockAccountClient(SiebelAccountClient)` |
| `app/services/icm/mock/admin.py` | `MockAdminClient(SiebelAdminClient)` |
| `app/services/icm/mock/attachments.py` | `MockAttachmentClient(SiebelAttachmentClient)` |
| `app/services/icm/mock/employment_plans.py` | `MockEPClient(SiebelEPClient)` |
| `app/services/icm/mock/monthly_report.py` | `MockMonthlyReportClient(SiebelMonthlyReportClient)` |
| `app/services/icm/mock/notifications.py` | `MockNotificationClient(SiebelNotificationClient)` |
| `app/services/icm/mock/payment.py` | `MockPaymentClient(SiebelPaymentClient)` |
| `app/services/icm/mock/profile.py` | `MockProfileClient(SiebelProfileClient)` |
| `app/services/icm/mock/registration.py` | `MockRegistrationClient(SiebelRegistrationClient)` |
| `app/services/icm/mock/service_requests.py` | `MockSRClient(SiebelSRClient)` |
| `scripts/seed_db.py` | Standalone async script — seeds DB and prints JWT tokens |
| `tests/test_mock_icm.py` | Tests for mock client injection and data shapes |
| `tests/test_seed.py` | Tests for DB seeder logic |

### Modified files

| File | Change |
|---|---|
| `app/services/icm/deps.py` | Add `_use_mock()`, refactor `_icm_kwargs()` to use `get_settings()`, update `get_siebel_client()` and `clear_clients()` |
| `docs/onboarding/local-dev-setup.md` | Add "Seed Data & Mock Mode" section after "Run Alembic Migrations" |

---

## Persona Constants (used across all tasks)

These stable IDs are referenced throughout the plan. Define them once in `data.py`.

```python
# User IDs (deterministic UUIDs for reproducibility)
ALICE_USER_ID = "a0000000-0000-0000-0000-000000000001"
BOB_USER_ID   = "b0000000-0000-0000-0000-000000000002"
CAROL_USER_ID = "c0000000-0000-0000-0000-000000000003"

# BCeID GUIDs
ALICE_BCEID = "alice-bceid-1001"
BOB_BCEID   = "bob-bceid-1002"
CAROL_BCEID = "carol-bceid-1003"

# Profile IDs
ALICE_PROFILE_ID = "a1000000-0000-0000-0000-000000000001"
BOB_PROFILE_ID   = "b1000000-0000-0000-0000-000000000002"
CAROL_PROFILE_ID = "c1000000-0000-0000-0000-000000000003"

# Portal IDs
ALICE_PORTAL_ID = "PTL-ALICE-001"
BOB_PORTAL_ID   = "PTL-BOB-002"
CAROL_PORTAL_ID = "PTL-CAROL-003"

# MIS Person IDs
ALICE_MIS_ID = "MIS-001"
BOB_MIS_ID   = "MIS-002"
CAROL_MIS_ID = "MIS-003"

# Case numbers
ALICE_CASE = "100100"
BOB_CASE   = "100200"
CAROL_CASE = "100300"

# Worker
WORKER_IDIR = "jsmith"
```

---

## Task 1: Mock data module

**Files:**
- Create: `app/services/icm/mock/data.py`

This is the foundation — all canned response data lives here. No behavior to test directly; subsequent tasks test this data through mock clients.

- [ ] **Step 1: Create `app/services/icm/mock/` package directory**

```bash
mkdir -p app/services/icm/mock
```

- [ ] **Step 2: Create `data.py` with persona constants and all canned responses**

Create `app/services/icm/mock/data.py` with the following structure. Every response dict should match the shape that the real Siebel API returns (as consumed by the domain services).

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add app/services/icm/mock/data.py
git commit -m "feat: add canned response data for mock ICM clients"
```

---

## Task 2: Mock client classes

**Files:**
- Create: `app/services/icm/mock/account.py`
- Create: `app/services/icm/mock/profile.py`
- Create: `app/services/icm/mock/payment.py`
- Create: `app/services/icm/mock/notifications.py`
- Create: `app/services/icm/mock/service_requests.py`
- Create: `app/services/icm/mock/monthly_report.py`
- Create: `app/services/icm/mock/employment_plans.py`
- Create: `app/services/icm/mock/registration.py`
- Create: `app/services/icm/mock/admin.py`
- Create: `app/services/icm/mock/attachments.py`
- Create: `app/services/icm/mock/__init__.py`

All mock clients follow the same pattern:
1. Inherit from the real client class
2. Override `__init__` to take no args and skip parent init
3. Include `async def aclose(self) -> None: pass` so the app lifespan shutdown doesn't error (parent's `aclose` needs `self._http` which mock clients don't have)
4. Override every method to return canned data from `data.py`
5. Log a warning for any method that lacks specific canned data

- [ ] **Step 1: Create `app/services/icm/mock/account.py`**

```python
import structlog
from app.services.icm.account import SiebelAccountClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAccountClient(SiebelAccountClient):
    def __init__(self):
        pass  # skip parent's HTTP/OAuth setup

    async def aclose(self) -> None:
        pass  # no HTTP client to close

    async def get_profile(self, user_id: str) -> dict:
        profile = data.ACCOUNT_PROFILES.get(user_id)
        if profile:
            return profile
        logger.warning("mock_unknown_id", method="get_profile", user_id=user_id)
        return dict(data.ACCOUNT_PROFILES[data.ALICE_USER_ID], user_id=user_id)

    async def update_contact(self, user_id: str, data: dict) -> dict:
        return {"status": "ok", "user_id": user_id, **data}

    async def get_case_members(self, user_id: str) -> dict:
        return data.CASE_MEMBERS.get(user_id, data.CASE_MEMBERS[data.ALICE_USER_ID])

    async def sync_profile(self, user_id: str) -> dict:
        return {"status": "ok", "user_id": user_id}

    async def validate_pin(self, user_id: str, pin: str) -> dict:
        return {"status": "ok", "valid": True}

    async def change_pin(self, user_id: str, new_pin: str) -> dict:
        return {"status": "ok"}

    async def request_pin_reset(self, user_id: str, email: str) -> dict:
        return {"status": "ok", "message": "PIN reset email sent"}

    async def confirm_pin_reset(self, token: str, new_pin: str) -> dict:
        return {"status": "ok", "message": "PIN has been reset"}
```

- [ ] **Step 2: Create `app/services/icm/mock/profile.py`**

```python
import structlog
from app.services.icm.profile import SiebelProfileClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockProfileClient(SiebelProfileClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_tombstone(self, bceid_guid: str) -> dict:
        return data.TOMBSTONES.get(bceid_guid, data.TOMBSTONES[data.ALICE_BCEID])

    async def validate_pin(self, bceid_guid: str, pin: str) -> dict:
        return {"status": "ok", "valid": True}

    async def update_tombstone(self, bceid_guid: str, data: dict) -> dict:
        return {"status": "ok", "bceid_guid": bceid_guid, **data}

    async def get_profile(self, bceid_guid: str) -> dict:
        return data.PROFILE_DATA.get(bceid_guid, data.PROFILE_DATA[data.ALICE_BCEID])

    async def link_profile(self, bceid_guid: str, link_data: dict) -> dict:
        return {"status": "ok", "bceid_guid": bceid_guid, "linked": True}

    async def has_newer_profile(self, bceid_guid: str) -> dict:
        return {"has_newer": False}

    async def get_banners(self, case_number: str) -> dict:
        return data.BANNERS.get(case_number, {"banners": []})
```

- [ ] **Step 3: Create `app/services/icm/mock/payment.py`**

```python
import structlog
from app.services.icm.payment import SiebelPaymentClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockPaymentClient(SiebelPaymentClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_payment_info(self, case_number: str) -> dict:
        info = data.PAYMENT_INFO.get(case_number, data.PAYMENT_INFO[data.ALICE_CASE])
        info = dict(info)
        info["upcoming_benefit_date"] = (data._today().replace(day=20)).isoformat()
        return info

    async def get_cheque_schedule(self, case_number: str) -> dict:
        return data._cheque_schedule(case_number)

    async def get_t5007_slips(self, profile_id: str) -> dict:
        return data.T5007_SLIPS.get(profile_id, {"slips": []})

    async def get_t5_history_years(self, profile_id: str) -> dict:
        return data.T5_HISTORY_YEARS.get(profile_id, {"years": []})

    async def get_mis_data(self, profile_id: str) -> dict:
        return data.MIS_DATA.get(profile_id, data.MIS_DATA[data.ALICE_PROFILE_ID])

    async def get_t5007_pdf(self, profile_id: str, year: int) -> dict:
        return {"pdf_data": data.MOCK_PDF_BASE64, "filename": f"T5007_{year}.pdf"}
```

- [ ] **Step 4: Create `app/services/icm/mock/notifications.py`**

```python
import structlog
from app.services.icm.notifications import SiebelNotificationClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockNotificationClient(SiebelNotificationClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_banners(self, case_number: str) -> dict:
        return data.BANNERS.get(case_number, {"banners": []})

    async def get_messages(self, profile_id: str, page: int = 1) -> dict:
        return data.MESSAGES.get(profile_id, {"messages": [], "total": 0})

    async def get_message_detail(self, message_id: str) -> dict:
        detail = data.MESSAGE_DETAILS.get(message_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_message_detail", message_id=message_id)
        return {"message_id": message_id, "subject": "Unknown", "body": "Mock message not found", "sent_date": data._now().isoformat(), "is_read": True, "can_reply": False, "message_type": "GENERAL", "attachments": []}

    async def mark_read(self, message_id: str) -> dict:
        return {"status": "ok", "message_id": message_id}

    async def send_message(self, message_data: dict) -> dict:
        return {"status": "ok", "message_id": f"MSG-NEW-{data.uuid4().hex[:6]}"}

    async def delete_message(self, msg_id: str) -> dict:
        return {"status": "ok", "message_id": msg_id}

    async def sign_and_send(self, msg_id: str, pin: str) -> dict:
        return {"status": "ok", "message_id": msg_id, "signed_at": data._now().isoformat()}
```

- [ ] **Step 5: Create `app/services/icm/mock/service_requests.py`**

```python
import structlog
from app.services.icm.service_requests import SiebelSRClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockSRClient(SiebelSRClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def create_sr(self, sr_type: str, profile_id: str) -> dict:
        new_id = f"SR-NEW-{data.uuid4().hex[:6]}"
        return {"sr_id": new_id, "sr_type": sr_type, "sr_number": new_id, "status": "Open", "created_at": data._now().isoformat()}

    async def get_sr_list(self, profile_id: str) -> dict:
        return data.SR_LISTS.get(profile_id, {"items": [], "total": 0, "page": 1, "page_size": 10})

    async def get_sr_detail(self, sr_id: str) -> dict:
        detail = data.SR_DETAILS.get(sr_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_sr_detail", sr_id=sr_id)
        return {"sr_id": sr_id, "sr_type": "ASSIST", "sr_number": sr_id, "status": "Open", "client_name": "Unknown", "created_at": data._now().isoformat(), "answers": {}, "attachments": []}

    async def cancel_sr(self, sr_id: str, reason: str) -> dict:
        return {"status": "ok", "sr_id": sr_id, "new_status": "Cancelled"}

    async def get_return_action(self, sr_type: str) -> dict:
        return data.SR_RETURN_ACTIONS.get(sr_type, {"sr_type": sr_type, "action": "submit", "requires_pin": True})

    async def get_eligible_types(self, profile_id: str, case_status: str) -> dict:
        return data.ELIGIBLE_SR_TYPES.get(case_status, {"types": []})

    async def finalize_sr_form(self, sr_id: str, answers: dict) -> dict:
        return {"status": "ok", "sr_id": sr_id}
```

- [ ] **Step 6: Create `app/services/icm/mock/monthly_report.py`**

```python
import structlog
from app.services.icm.monthly_report import SiebelMonthlyReportClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockMonthlyReportClient(SiebelMonthlyReportClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_report_period(self, case_number: str) -> dict:
        return data._report_period(case_number)

    async def submit_monthly_report(self, sd81_id: str, submission_data: dict, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id, "new_status": "SUB", "submitted_at": data._now().isoformat()}

    async def get_ia_questionnaire(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return data.QUESTIONNAIRE

    async def list_reports(self, profile_id: str, days_ago: int) -> dict:
        return data.MONTHLY_REPORTS.get(profile_id, {"reports": [], "total": 0})

    async def start_report(self, profile_id: str) -> dict:
        new_id = f"SD81-NEW-{data.uuid4().hex[:6]}"
        return {"sd81_id": new_id, "benefit_month": data._today().replace(day=1).isoformat(), "status": "PRT"}

    async def finalize(self, sd81_id: str, answers: dict, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id}

    async def restart_report(self, sd81_id: str, *, profile_id: str | None = None) -> dict:
        return {"status": "ok", "sd81_id": sd81_id, "new_status": "RST"}

    async def get_summary(self, sd81_id: str) -> dict:
        return data.REPORT_SUMMARY.get(sd81_id, {"sd81_id": sd81_id, "benefit_month": data._today().replace(day=1).isoformat(), "status": "PRT", "answers": {}})

    async def get_report_pdf(self, sd81_id: str, *, profile_id: str | None = None) -> bytes:
        return data.MOCK_PDF_BYTES
```

- [ ] **Step 7: Create `app/services/icm/mock/employment_plans.py`**

```python
import structlog
from app.services.icm.employment_plans import SiebelEPClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockEPClient(SiebelEPClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def get_ep_list(self, profile_id: str) -> dict:
        return data.EP_LISTS.get(profile_id, {"plans": []})

    async def get_ep_detail(self, ep_id: str) -> dict:
        detail = data.EP_DETAILS.get(ep_id)
        if detail:
            return detail
        logger.warning("mock_unknown_id", method="get_ep_detail", ep_id=ep_id)
        return {"ep_id": ep_id, "status": "SUBMITTED", "plan_date": data._today().isoformat(), "message_deleted": False}

    async def sign_ep(self, ep_id: str, signature_data: dict) -> dict:
        return {"status": "ok", "ep_id": ep_id, "signed_at": data._now().isoformat()}

    async def send_to_icm(self, ep_id: str, pin: str) -> dict:
        return {"status": "ok", "ep_id": ep_id, "sent_at": data._now().isoformat()}

    async def mark_form_submitted(self, ep_id: str, msg_id: int) -> dict:
        return {"status": "ok", "ep_id": ep_id, "msg_id": msg_id}
```

- [ ] **Step 8: Create `app/services/icm/mock/registration.py`**

```python
from app.services.icm.registration import SiebelRegistrationClient
from app.services.icm.mock import data


class MockRegistrationClient(SiebelRegistrationClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def register_new_applicant(self, registrant_data: dict) -> dict:
        return data.REGISTRATION_RESPONSES["new"]

    async def register_existing_client(self, link_data: dict) -> dict:
        return data.REGISTRATION_RESPONSES["existing"]

    async def get_link_options(self, bceid_guid: str) -> dict:
        return data.LINK_OPTIONS.get(bceid_guid, {"options": []})
```

- [ ] **Step 9: Create `app/services/icm/mock/admin.py`**

```python
import structlog
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAdminClient(SiebelAdminClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def search_profiles(self, first_name: str | None, last_name: str | None, sin: str | None, page: int) -> dict:
        # Simple filter: if a name is provided, filter results
        results = data.ADMIN_SEARCH_RESULTS["results"]
        if first_name:
            results = [r for r in results if first_name.lower() in r["full_name"].lower()]
        if last_name:
            results = [r for r in results if last_name.lower() in r["full_name"].lower()]
        return {"results": results, "total": len(results), "page": page, "page_size": 10}

    async def get_client_profile(self, client_bceid_guid: str) -> dict:
        return data.ADMIN_CLIENT_PROFILES.get(client_bceid_guid, data.ADMIN_CLIENT_PROFILES[data.ALICE_BCEID])

    async def get_worker_permissions(self, idir_username: str) -> dict:
        return data.WORKER_PERMISSIONS.get(idir_username, {"idir_username": idir_username, "permissions": []})

    async def validate_ao_login(self, sr_number: str, sin: str) -> dict:
        return {"sr_number": sr_number, "applicant_name": "Alice Thompson", "case_status": "Active"}
```

- [ ] **Step 10: Create `app/services/icm/mock/attachments.py`**

```python
import structlog
from app.services.icm.attachments import SiebelAttachmentClient
from app.services.icm.mock import data

logger = structlog.get_logger()


class MockAttachmentClient(SiebelAttachmentClient):
    def __init__(self):
        pass

    async def aclose(self) -> None:
        pass

    async def upload_attachment(self, sr_id: str, file_data: dict) -> dict:
        att_id = f"ATT-NEW-{data.uuid4().hex[:6]}"
        return {"attachment_id": att_id, "sr_id": sr_id, "filename": file_data.get("filename", "uploaded.pdf"), "uploaded_at": data._now().isoformat()}

    async def get_attachment(self, attachment_id: str) -> dict:
        return data.ATTACHMENT_METADATA.get(attachment_id, {"attachment_id": attachment_id, "filename": "unknown.pdf", "mime_type": "application/pdf", "size_bytes": 0, "uploaded_at": data._now().isoformat()})

    async def delete_sr_attachment(self, sr_id: str, attachment_id: str) -> dict:
        return {"status": "ok", "sr_id": sr_id, "attachment_id": attachment_id}

    async def get_message_attachment(self, profile_id: str, msg_id: str, attachment_id: str) -> dict:
        return data.ATTACHMENT_METADATA.get(attachment_id, {"attachment_id": attachment_id, "filename": "message_attachment.pdf", "mime_type": "application/pdf", "size_bytes": 0})

    async def get_sr_attachment(self, profile_id: str, sr_id: str) -> dict:
        return {"sr_id": sr_id, "profile_id": profile_id, "attachments": []}
```

- [ ] **Step 11: Create `app/services/icm/mock/__init__.py`**

```python
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
```

- [ ] **Step 12: Commit**

```bash
git add app/services/icm/mock/
git commit -m "feat: add mock ICM client classes for all 10 Siebel clients"
```

---

## Task 3: Update `deps.py` with mock injection

**Files:**
- Modify: `app/services/icm/deps.py`
- Test: `tests/test_mock_icm.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mock_icm.py`:

```python
"""Tests for mock ICM client injection."""

import os
import pytest
from unittest.mock import patch

from app.services.icm.deps import get_siebel_client, clear_clients, _use_mock
from app.services.icm.payment import SiebelPaymentClient
from app.services.icm.account import SiebelAccountClient
from app.services.icm.mock.payment import MockPaymentClient
from app.services.icm.mock.account import MockAccountClient


@pytest.fixture(autouse=True)
def _clean_clients():
    """Reset client cache between tests."""
    clear_clients()
    yield
    clear_clients()


class TestUseMock:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_true_when_local_and_no_base_url(self):
        # get_settings is lru_cached, so we need to clear it
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is True
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": "https://icm.example.com"})
    def test_returns_false_when_base_url_set(self):
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is False
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "ICM_BASE_URL": "https://icm.example.com", "JWT_SECRET": "strong-secret-123456", "ICM_CLIENT_ID": "id", "ICM_CLIENT_SECRET": "sec", "ICM_TOKEN_URL": "https://tok"})
    def test_returns_false_when_not_local(self):
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is False
        get_settings.cache_clear()


class TestMockClientInjection:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_mock_payment_client_in_local_mode(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client = get_siebel_client(SiebelPaymentClient)
        assert isinstance(client, MockPaymentClient)
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_mock_account_client_in_local_mode(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client = get_siebel_client(SiebelAccountClient)
        assert isinstance(client, MockAccountClient)
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_caches_mock_clients(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client1 = get_siebel_client(SiebelPaymentClient)
        client2 = get_siebel_client(SiebelPaymentClient)
        assert client1 is client2
        get_settings.cache_clear()


class TestMockClientData:
    """Verify mock clients return expected data shapes."""

    @pytest.mark.asyncio
    async def test_payment_info_has_required_fields(self):
        client = MockPaymentClient()
        result = await client.get_payment_info("100100")
        assert "assistance_type" in result
        assert "mis_data" in result
        assert "allowances" in result["mis_data"]

    @pytest.mark.asyncio
    async def test_account_profile_has_required_fields(self):
        from app.services.icm.mock.data import ALICE_USER_ID
        client = MockAccountClient()
        result = await client.get_profile(ALICE_USER_ID)
        assert result["first_name"] == "Alice"
        assert result["case_status"] == "Active"
        assert "phone_numbers" in result

    @pytest.mark.asyncio
    async def test_unknown_id_returns_fallback(self):
        client = MockAccountClient()
        result = await client.get_profile("nonexistent-id")
        # Should return Alice's data as fallback
        assert result["first_name"] == "Alice"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_mock_icm.py -v
```

Expected: FAIL — `_use_mock` not yet defined in `deps.py`.

- [ ] **Step 3: Update `app/services/icm/deps.py`**

Replace the full file content with:

```python
import structlog
from typing import TypeVar, Type
from app.config import get_settings
from app.services.icm.client import ICMClient

logger = structlog.get_logger()

T = TypeVar("T", bound=ICMClient)

_clients: dict[type, ICMClient] = {}
_MOCK_MAP: dict[type, type] = {}


def _icm_kwargs() -> dict:
    settings = get_settings()
    return {
        "base_url": settings.icm_base_url,
        "client_id": settings.icm_client_id,
        "client_secret": settings.icm_client_secret,
        "token_url": settings.icm_token_url,
    }


def _use_mock() -> bool:
    settings = get_settings()
    return settings.environment == "local" and not settings.icm_base_url


def get_siebel_client(cls: Type[T]) -> T:
    if _use_mock():
        if not _MOCK_MAP:
            from app.services.icm.mock import MOCK_CLIENT_MAP
            _MOCK_MAP.update(MOCK_CLIENT_MAP)
            logger.info("mock_icm_enabled", msg="Using mock ICM clients — Siebel calls will return canned data")
        mock_cls = _MOCK_MAP.get(cls)
        if mock_cls:
            if cls not in _clients:
                _clients[cls] = mock_cls()
            return _clients[cls]  # type: ignore[return-value]
    if cls not in _clients:
        _clients[cls] = cls(**_icm_kwargs())
    return _clients[cls]  # type: ignore[return-value]


def clear_clients() -> None:
    """Clear the client cache. Call in test fixtures for isolation."""
    _clients.clear()
    _MOCK_MAP.clear()


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_mock_icm.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest -v
```

Expected: No regressions. Existing tests should still pass since `_use_mock()` returns `False` in test environments (ENVIRONMENT defaults to "local" but some tests override it; the key is that existing tests don't depend on ICM_BASE_URL being set).

- [ ] **Step 6: Commit**

```bash
git add app/services/icm/deps.py tests/test_mock_icm.py
git commit -m "feat: add mock ICM client injection in deps.py with tests"
```

---

## Task 4: DB seeder script

**Files:**
- Create: `scripts/seed_db.py`

- [ ] **Step 1: Create the scripts directory and `scripts/seed_db.py`**

```bash
mkdir -p scripts
```

```python
#!/usr/bin/env python3
"""
Seed the local database with test data for development.

Usage:
    python scripts/seed_db.py          # idempotent insert
    python scripts/seed_db.py --reset  # truncate and re-insert

Requires DATABASE_URL and JWT_SECRET in environment (or .env file).
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta, UTC
from uuid import UUID

# Ensure the project root is on sys.path so app.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt as pyjwt
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, Profile
from app.models.registration import RegistrationSession
from app.models.ao_registration import AORegistrationSession
from app.models.auth_tokens import PINResetToken
from app.models.service_requests import SRDraft
from app.models.attachments import AttachmentRecord, ScanJob
from app.models.employment import PlanSignatureSession
from app.models.misc import DisclaimerAcknowledgement
from app.models.audit import WorkerAuditRecord

# ---------------------------------------------------------------------------
# Persona constants (must match app/services/icm/mock/data.py)
# ---------------------------------------------------------------------------

ALICE_USER_ID = UUID("a0000000-0000-0000-0000-000000000001")
BOB_USER_ID = UUID("b0000000-0000-0000-0000-000000000002")
CAROL_USER_ID = UUID("c0000000-0000-0000-0000-000000000003")

ALICE_BCEID = "alice-bceid-1001"
BOB_BCEID = "bob-bceid-1002"
CAROL_BCEID = "carol-bceid-1003"

ALICE_PROFILE_ID = UUID("a1000000-0000-0000-0000-000000000001")
BOB_PROFILE_ID = UUID("b1000000-0000-0000-0000-000000000002")
CAROL_PROFILE_ID = UUID("c1000000-0000-0000-0000-000000000003")

WORKER_IDIR = "jsmith"

now = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _get_db_url() -> str:
    """Read DATABASE_URL the same way the app does."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "change-me-in-production")


def _make_jwt(sub: str, role: str, *, bceid_guid: str | None = None, idir_username: str | None = None) -> str:
    payload: dict = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=24),
    }
    if bceid_guid:
        payload["bceid_guid"] = bceid_guid
    if idir_username:
        payload["idir_username"] = idir_username
    return pyjwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_users(session: AsyncSession) -> bool:
    """Create 3 test users. Returns True if created, False if already exist."""
    existing = await session.get(User, ALICE_USER_ID)
    if existing:
        print("  Users already exist, skipping.")
        return False

    users = [
        User(id=ALICE_USER_ID, bceid_guid=ALICE_BCEID, created_at=now, updated_at=now),
        User(id=BOB_USER_ID, bceid_guid=BOB_BCEID, created_at=now, updated_at=now),
        User(id=CAROL_USER_ID, bceid_guid=CAROL_BCEID, created_at=now, updated_at=now),
    ]
    session.add_all(users)
    print("  Created 3 users: Alice, Bob, Carol")
    return True


async def seed_profiles(session: AsyncSession) -> None:
    existing = await session.get(Profile, ALICE_PROFILE_ID)
    if existing:
        print("  Profiles already exist, skipping.")
        return

    profiles = [
        Profile(
            id=ALICE_PROFILE_ID, user_id=ALICE_USER_ID,
            portal_id="PTL-ALICE-001", link_code="LINKED",
            mis_person_id="MIS-001", created_at=now, updated_at=now,
        ),
        Profile(
            id=BOB_PROFILE_ID, user_id=BOB_USER_ID,
            portal_id="PTL-BOB-002", link_code="LINKED",
            mis_person_id="MIS-002", created_at=now, updated_at=now,
        ),
        Profile(
            id=CAROL_PROFILE_ID, user_id=CAROL_USER_ID,
            portal_id="PTL-CAROL-003", link_code="UNLINKED",
            mis_person_id="MIS-003", created_at=now, updated_at=now,
        ),
    ]
    session.add_all(profiles)
    print("  Created 3 profiles: Alice=LINKED, Bob=LINKED, Carol=UNLINKED")


async def seed_registration_sessions(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM registrationsession WHERE invite_token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  Registration sessions already exist, skipping.")
        return

    sessions = [
        RegistrationSession(
            user_id=ALICE_USER_ID,
            invite_token="seed-invite-alice-completed",
            step=6,
            form_state_json={"account_creation_type": "SELF", "completed": True},
            expires_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=2),
        ),
        RegistrationSession(
            invite_token="seed-invite-in-progress",
            step=3,
            form_state_json={"account_creation_type": "SELF", "first_name": "New", "last_name": "Applicant"},
            expires_at=now + timedelta(hours=24),
        ),
    ]
    session.add_all(sessions)
    print("  Created 2 registration sessions: 1 completed, 1 in-progress")


async def seed_pin_reset_tokens(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM pinresettoken WHERE token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  PIN reset tokens already exist, skipping.")
        return

    tokens = [
        PINResetToken(
            profile_id=ALICE_PROFILE_ID,
            token="seed-pin-reset-active",
            expires_at=now + timedelta(hours=1),
        ),
        PINResetToken(
            profile_id=BOB_PROFILE_ID,
            token="seed-pin-reset-expired",
            expires_at=now - timedelta(hours=24),
            used_at=now - timedelta(hours=25),
        ),
    ]
    session.add_all(tokens)
    print("  Created 2 PIN reset tokens: 1 active, 1 expired")


async def seed_ao_registration(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM aoregistrationsession WHERE worker_idir = :idir"),
        {"idir": WORKER_IDIR},
    )
    if result.scalar() > 0:
        print("  AO registration session already exists, skipping.")
        return

    test_sin = "000000000"
    sin_hash = bcrypt.hashpw(test_sin.encode(), bcrypt.gensalt()).decode()

    ao_session = AORegistrationSession(
        worker_idir=WORKER_IDIR,
        applicant_sr_num="SR-AO-001",
        applicant_sin_hash=sin_hash,
        step_reached=1,
        expires_at=now + timedelta(hours=4),
    )
    session.add(ao_session)
    print("  Created 1 AO registration session (test SIN: 000-000-000)")


async def seed_sr_drafts(session: AsyncSession) -> None:
    existing = await session.get(SRDraft, "seed-sr-alice-assist")
    if existing:
        print("  SR drafts already exist, skipping.")
        return

    drafts = [
        SRDraft(
            sr_id="seed-sr-alice-assist",
            user_id=str(ALICE_USER_ID),
            sr_type="ASSIST",
            draft_json={"employment_status": "unemployed", "seeking_employment": True},
            updated_at=now,
        ),
        SRDraft(
            sr_id="seed-sr-alice-crisis",
            user_id=str(ALICE_USER_ID),
            sr_type="CRISIS_FOOD",
            draft_json={},
            updated_at=now,
        ),
        SRDraft(
            sr_id="seed-sr-bob-dd",
            user_id=str(BOB_USER_ID),
            sr_type="DIRECT_DEPOSIT",
            draft_json={"bank_name": "TD Canada Trust", "transit_number": "00123"},
            updated_at=now,
        ),
    ]
    session.add_all(drafts)
    print("  Created 3 SR drafts: ASSIST, CRISIS_FOOD (Alice), DIRECT_DEPOSIT (Bob)")


async def seed_attachments(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM attachmentrecord WHERE storage_path LIKE 'seed/%'")
    )
    if result.scalar() > 0:
        print("  Attachments already exist, skipping.")
        return

    att_alice = AttachmentRecord(
        profile_id=ALICE_PROFILE_ID,
        sr_draft_id="seed-sr-alice-assist",
        filename="proof_of_income.pdf",
        mime_type="application/pdf",
        size_bytes=45000,
        storage_path="seed/alice/proof_of_income.pdf",
        av_status="CLEAN",
        uploaded_at=now,
    )
    att_bob = AttachmentRecord(
        profile_id=BOB_PROFILE_ID,
        sr_draft_id="seed-sr-bob-dd",
        filename="bank_statement.pdf",
        mime_type="application/pdf",
        size_bytes=128000,
        storage_path="seed/bob/bank_statement.pdf",
        av_status="PENDING",
        uploaded_at=now,
    )
    att_carol = AttachmentRecord(
        profile_id=CAROL_PROFILE_ID,
        filename="suspicious_file.exe",
        mime_type="application/octet-stream",
        size_bytes=666,
        storage_path="seed/carol/suspicious_file.exe",
        av_status="INFECTED",
        uploaded_at=now,
    )
    session.add_all([att_alice, att_bob, att_carol])
    await session.flush()  # get IDs

    scans = [
        ScanJob(attachment_id=att_alice.id, status="CLEAN", scanned_at=now),
        ScanJob(attachment_id=att_bob.id, status="QUEUED"),
        ScanJob(attachment_id=att_carol.id, status="INFECTED", scanned_at=now),
    ]
    session.add_all(scans)
    print("  Created 3 attachments + scan jobs: CLEAN, PENDING, INFECTED")


async def seed_plan_signatures(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM plansignaturesession WHERE token LIKE 'seed-%'")
    )
    if result.scalar() > 0:
        print("  Plan signature sessions already exist, skipping.")
        return

    sigs = [
        PlanSignatureSession(
            profile_id=BOB_PROFILE_ID,
            ep_id="EP-B001",
            token="seed-ep-unsigned",
            expires_at=now + timedelta(hours=2),
        ),
        PlanSignatureSession(
            profile_id=BOB_PROFILE_ID,
            ep_id="EP-B002",
            token="seed-ep-signed",
            expires_at=now + timedelta(hours=24),
            signed_at=now - timedelta(hours=12),
        ),
    ]
    session.add_all(sigs)
    print("  Created 2 plan signature sessions: 1 unsigned, 1 signed")


async def seed_disclaimer(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM disclaimeracknowledgement WHERE session_id = 'seed-session'")
    )
    if result.scalar() > 0:
        print("  Disclaimer acknowledgement already exists, skipping.")
        return

    ack = DisclaimerAcknowledgement(session_id="seed-session", acknowledged_at=now)
    session.add(ack)
    print("  Created 1 disclaimer acknowledgement")


async def seed_audit_records(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT count(*) FROM workerauditrecord WHERE worker_idir = :idir"),
        {"idir": WORKER_IDIR},
    )
    if result.scalar() > 0:
        print("  Audit records already exist, skipping.")
        return

    records = [
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/admin/clients", resource_type="client_search",
            timestamp=now - timedelta(hours=3), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/admin/clients/alice-bceid-1001",
            resource_type="client_profile", resource_id=ALICE_BCEID,
            client_bceid_guid=ALICE_BCEID,
            timestamp=now - timedelta(hours=2), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="POST /api/account/validate-pin",
            resource_type="pin_validation", resource_id=str(ALICE_USER_ID),
            client_bceid_guid=ALICE_BCEID,
            timestamp=now - timedelta(hours=1, minutes=30), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SSBC_WORKER",
            action="GET /api/service-requests",
            resource_type="sr_list", resource_id=str(BOB_USER_ID),
            client_bceid_guid=BOB_BCEID,
            timestamp=now - timedelta(hours=1), request_ip="10.0.0.1",
        ),
        WorkerAuditRecord(
            worker_idir=WORKER_IDIR, worker_role="SUPER_ADMIN",
            action="POST /api/admin/ao/validate",
            resource_type="ao_registration",
            timestamp=now - timedelta(minutes=30), request_ip="10.0.0.2",
        ),
    ]
    session.add_all(records)
    print("  Created 5 worker audit records")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

# Tables in FK-safe truncation order (children before parents)
TRUNCATE_ORDER = [
    "scanjob",
    "attachmentrecord",
    "plansignaturesession",
    "pinresettoken",
    "sr_drafts",
    "workerauditrecord",
    "disclaimeracknowledgement",
    "aoregistrationsession",
    "registrationsession",
    "profile",
    "user",
]


async def reset_seed_data(session: AsyncSession) -> None:
    """Truncate all seeded tables in FK-safe order."""
    print("\nResetting seed data...")
    for table in TRUNCATE_ORDER:
        await session.execute(text(f"DELETE FROM {table}"))
        print(f"  Cleared {table}")
    await session.commit()
    print("Reset complete.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(reset: bool = False) -> None:
    db_url = _get_db_url()
    print(f"Database: {db_url}")

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]

    async with async_session() as session:
        if reset:
            await reset_seed_data(session)

        print("\nSeeding database...")
        await seed_users(session)
        await seed_profiles(session)
        await seed_registration_sessions(session)
        await seed_pin_reset_tokens(session)
        await seed_ao_registration(session)
        await seed_sr_drafts(session)
        await seed_attachments(session)
        await seed_plan_signatures(session)
        await seed_disclaimer(session)
        await seed_audit_records(session)
        await session.commit()

    await engine.dispose()

    # Print summary
    print("\n" + "=" * 50)
    print("  SEED DATA SUMMARY")
    print("=" * 50)
    print()
    print("Personas:")
    print(f"  Alice Thompson  bceid_guid={ALICE_BCEID}  user_id={ALICE_USER_ID}")
    print(f"  Bob Chen        bceid_guid={BOB_BCEID}    user_id={BOB_USER_ID}")
    print(f"  Carol Williams  bceid_guid={CAROL_BCEID}  user_id={CAROL_USER_ID}")
    print(f"  Worker          idir={WORKER_IDIR}")
    print()
    print("JWT tokens (valid 24h — paste into Swagger UI Authorize dialog):")
    print()
    print(f"  Alice:  {_make_jwt(str(ALICE_USER_ID), 'CLIENT', bceid_guid=ALICE_BCEID)}")
    print()
    print(f"  Bob:    {_make_jwt(str(BOB_USER_ID), 'CLIENT', bceid_guid=BOB_BCEID)}")
    print()
    print(f"  Carol:  {_make_jwt(str(CAROL_USER_ID), 'CLIENT', bceid_guid=CAROL_BCEID)}")
    print()
    print(f"  Worker: {_make_jwt(WORKER_IDIR, 'WORKER', idir_username=WORKER_IDIR)}")
    print()
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the local development database")
    parser.add_argument("--reset", action="store_true", help="Truncate all seed data before re-inserting")
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset))
```

- [ ] **Step 2: Verify the seeder runs against a local database**

```bash
# Ensure DB is set up (either SQLite or PostgreSQL)
source .venv/bin/activate
alembic upgrade head
python scripts/seed_db.py
```

Expected: Summary output showing all records created and JWT tokens printed.

- [ ] **Step 3: Verify idempotency — run again**

```bash
python scripts/seed_db.py
```

Expected: Every section prints "already exist, skipping." and no duplicates are created.

- [ ] **Step 4: Verify `--reset` flag**

```bash
python scripts/seed_db.py --reset
```

Expected: Truncates all tables, then re-seeds everything fresh.

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_db.py
git commit -m "feat: add database seeder script with 3 test personas and JWT tokens"
```

---

## Task 5: Test the seeder programmatically

**Files:**
- Create: `tests/test_seed.py`

- [ ] **Step 1: Write seeder tests**

Create `tests/test_seed.py`:

```python
"""Tests for the database seeder script."""

import pytest
import sys
import os
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from seed_db import (
    seed_users, seed_profiles, seed_sr_drafts, seed_attachments,
    ALICE_USER_ID, BOB_USER_ID, CAROL_USER_ID,
    ALICE_PROFILE_ID, ALICE_BCEID,
)
from app.models.user import User, Profile
from app.models.service_requests import SRDraft
from app.models.attachments import AttachmentRecord


@pytest.fixture
async def db_session():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]
    async with async_session() as session:
        yield session
    await engine.dispose()


class TestSeedUsers:
    @pytest.mark.asyncio
    async def test_creates_three_users(self, db_session):
        created = await seed_users(db_session)
        await db_session.commit()
        assert created is True
        alice = await db_session.get(User, ALICE_USER_ID)
        assert alice is not None
        assert alice.bceid_guid == ALICE_BCEID

    @pytest.mark.asyncio
    async def test_idempotent(self, db_session):
        await seed_users(db_session)
        await db_session.commit()
        created = await seed_users(db_session)
        assert created is False


class TestSeedProfiles:
    @pytest.mark.asyncio
    async def test_creates_profiles_linked_to_users(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await db_session.commit()
        profile = await db_session.get(Profile, ALICE_PROFILE_ID)
        assert profile is not None
        assert profile.user_id == ALICE_USER_ID
        assert profile.link_code == "LINKED"


class TestSeedSRDrafts:
    @pytest.mark.asyncio
    async def test_sr_draft_user_id_is_string(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await seed_sr_drafts(db_session)
        await db_session.commit()
        draft = await db_session.get(SRDraft, "seed-sr-alice-assist")
        assert draft is not None
        assert draft.user_id == str(ALICE_USER_ID)
        assert draft.sr_type == "ASSIST"


class TestSeedAttachments:
    @pytest.mark.asyncio
    async def test_creates_three_attachments_with_scan_jobs(self, db_session):
        await seed_users(db_session)
        await seed_profiles(db_session)
        await seed_sr_drafts(db_session)
        await seed_attachments(db_session)
        await db_session.commit()
        from sqlalchemy import text
        result = await db_session.execute(text("SELECT count(*) FROM attachmentrecord"))
        assert result.scalar() == 3
        result = await db_session.execute(text("SELECT count(*) FROM scanjob"))
        assert result.scalar() == 3
```

- [ ] **Step 2: Run seeder tests**

```bash
python -m pytest tests/test_seed.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_seed.py
git commit -m "test: add seeder unit tests for users, profiles, SR drafts, attachments"
```

---

## Task 6: Update local dev setup documentation

**Files:**
- Modify: `docs/onboarding/local-dev-setup.md`

- [ ] **Step 1: Add "Seed Data & Mock Mode" section**

Insert the following after the "Run Alembic Migrations" section (after line 100 of `docs/onboarding/local-dev-setup.md`) and before "Start the API Server":

```markdown
## Seed Data & Mock Mode

### Seed the database

After running migrations, populate the database with test data:

```bash
python scripts/seed_db.py
```

This creates three test personas with realistic, relationship-consistent data across all tables:

| Persona | BCeID GUID | Case | Scenario |
|---|---|---|---|
| Alice Thompson | `alice-bceid-1001` | #100100 (Active) | Single client, 1 dependant, 2 SR drafts, clean attachment |
| Bob Chen | `bob-bceid-1002` | #100200 (Active) | Couple (spouse: Maria), PWD, employment plan pending signature |
| Carol Williams | `carol-bceid-1003` | #100300 (Closed) | Unlinked profile, edge-case testing |

The seeder also prints **JWT tokens** for each persona (valid 24 hours). Paste these into Swagger UI's **Authorize** dialog to call authenticated endpoints.

The command is idempotent — running it again skips existing records. To start fresh:

```bash
python scripts/seed_db.py --reset
```

### Mock ICM / Siebel mode

When `ENVIRONMENT=local` and `ICM_BASE_URL` is empty (the default in the `.env` template above), the API automatically uses **mock ICM clients** that return canned data instead of calling the real Siebel REST services. This means:

- All API endpoints return realistic data without VPN access
- No Siebel credentials or connectivity required
- You can exercise the full UI workflow locally

Mock mode is confirmed in the server logs at startup:

```
mock_icm_enabled=true msg="Using mock ICM clients — Siebel calls will return canned data"
```

To disable mock mode and use real Siebel (requires VPN), set `ICM_BASE_URL` to the actual endpoint in your `.env`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/onboarding/local-dev-setup.md
git commit -m "docs: add seed data and mock ICM mode instructions to local dev setup"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest -v
```

Expected: All tests pass, including new tests in `test_mock_icm.py` and `test_seed.py`.

- [ ] **Step 2: Run linting**

```bash
ruff check .
```

Expected: No lint errors in new files. Fix any issues.

- [ ] **Step 3: Run type checking**

```bash
mypy app/
```

Expected: No new type errors. The mock clients may need `# type: ignore` on `__init__` since they skip the parent constructor — add these if mypy complains.

- [ ] **Step 4: End-to-end smoke test**

```bash
# Reset and re-seed
alembic upgrade head
python scripts/seed_db.py --reset

# Start the server
uvicorn app.main:app --reload --port 8000
```

Then in another terminal or browser:
1. Open http://localhost:8000/docs (Swagger UI)
2. Click **Authorize** and paste Alice's JWT token
3. Call `GET /api/payment/info` — should return Alice's mock payment data
4. Call `GET /api/notifications/messages` — should return Alice's mock messages

- [ ] **Step 5: Commit any fixes from verification**

If any fixes were needed during verification, commit them:

```bash
git add -A
git commit -m "fix: address issues found during final verification"
```
