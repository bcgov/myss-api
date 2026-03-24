# Seed Data & Mock ICM Design

**Date:** 2026-03-24
**Status:** Draft

## Goal

Give developers a fully functional local environment without VPN access to Siebel/ICM. Two deliverables:

1. **DB seeder** (`scripts/seed_db.py`) — populates all local database tables with realistic, relationship-consistent mock data.
2. **Mock ICM clients** (`app/services/icm/mock/`) — drop-in replacements for every Siebel client that return canned data instead of making HTTP calls.

Together these let a developer run `alembic upgrade head && python scripts/seed_db.py && uvicorn app.main:app --reload` and immediately exercise every API endpoint through Swagger UI with pre-generated JWT tokens.

## DB Seeder

### Location and invocation

`scripts/seed_db.py` — standalone async script.

```bash
python scripts/seed_db.py          # idempotent insert
python scripts/seed_db.py --reset  # truncate seed data, then re-insert
```

### Design decisions

- Uses the same `DATABASE_URL` from environment/config as the app.
- Idempotent: checks for existing records by known stable identifiers (e.g. `bceid_guid`) before inserting.
- `--reset` flag truncates all seeded tables (respecting FK order) before re-inserting, so developers can get back to a clean state.
- Prints a summary with user IDs, BCeID GUIDs, and pre-signed JWT tokens (24h expiry) for each persona.
- Uses the existing `PyJWT` library (already in `pyproject.toml`) to sign JWT tokens — no new dependencies.

### Implementation notes

- `sr_drafts.user_id` is a plain `str` column (not a UUID FK). The seeder must store `str(user.id)` when creating SR draft rows.
- `registrationsession.invite_token` is unique and non-nullable. Generate a UUID for each session. Set `expires_at` to 24h from seed time for in-progress sessions; any past time for completed ones. Set `completed_at` to a past timestamp for completed sessions.
- `aoregistrationsession.applicant_sin_hash` is a bcrypt hash. Use a well-known test SIN (`000-000-000`) and bcrypt-hash it so developers know the input value.
- `attachmentrecord.profile_id` is a required FK to `profile.id`. The INFECTED edge-case attachment is assigned to Carol (exercises her otherwise-sparse data).

### Seed data inventory

| Table | Records | Details |
|---|---|---|
| `user` | 3 | Alice (active single), Bob (active couple/PWD), Carol (closed case) |
| `profile` | 3 | Alice=LINKED, Bob=LINKED, Carol=UNLINKED |
| `registrationsession` | 2 | One completed (step 6, tied to Alice), one in-progress (step 3) |
| `pinresettoken` | 2 | One active (expires in 1 hour), one expired |
| `aoregistrationsession` | 1 | Active worker override session |
| `sr_drafts` | 3 | ASSIST (Alice, partial form), CRISIS_FOOD (Alice, empty), DIRECT_DEPOSIT (Bob, partial) |
| `attachmentrecord` + `scanjob` | 3 | CLEAN (Alice), PENDING (Bob), INFECTED (Carol) |
| `plansignaturesession` | 2 | One unsigned (Bob, expires in 2h), one signed (Bob, signed yesterday) |
| `disclaimeracknowledgement` | 1 | Anonymous session |
| `workerauditrecord` | 5 | Mix of GET/POST across account, SR, admin domains |
| `eligibility_rate_table` | 0 | Already seeded by migration 0003 — skip if rows exist |
| `eligibility_asset_limit` | 0 | Already seeded by migration 0003 — skip if rows exist |

### Persona details

**Alice Thompson** — `bceid_guid=alice-bceid-1001`
- Single client, active case #100100
- Portal ID: `PTL-ALICE-001`, MIS person ID: `MIS-001`
- Has 1 dependant (child)
- 2 SR drafts, 1 clean attachment
- Completed registration

**Bob Chen** — `bceid_guid=bob-bceid-1002`
- Couple with spouse Maria Chen, PWD designation, active case #100200
- Portal ID: `PTL-BOB-002`, MIS person ID: `MIS-002`
- Spouse + 2 dependants
- 1 SR draft (DIRECT_DEPOSIT), 1 pending attachment
- Employment plan pending signature

**Carol Williams** — `bceid_guid=carol-bceid-1003`
- Closed case, unlinked profile
- Portal ID: `PTL-CAROL-003`, MIS person ID: `MIS-003`
- Tests edge cases: limited data, no active SRs

**Worker** — `idir_username=jsmith`
- Used for admin/worker JWT token
- Audit records attributed to this IDIR

### JWT tokens

The seeder generates and prints JWT tokens for each persona using the app's `JWT_SECRET`. Tokens include:
- `user_id`, `role` (CLIENT or WORKER), `bceid_guid` or `idir_username`
- 24-hour expiry
- Directly pasteable into Swagger UI's Authorize dialog

## Mock ICM Clients

### File structure

```
app/services/icm/mock/
  __init__.py             # exports all mock client classes
  data.py                 # centralized canned response data
  account.py              # MockAccountClient
  admin.py                # MockAdminClient
  attachments.py          # MockAttachmentClient
  employment_plans.py     # MockEPClient
  monthly_report.py       # MockMonthlyReportClient
  notifications.py        # MockNotificationClient
  payment.py              # MockPaymentClient
  profile.py              # MockProfileClient
  registration.py         # MockRegistrationClient
  service_requests.py     # MockSRClient
```

### Client design

Each mock client:
- Inherits from its real counterpart (e.g. `MockPaymentClient(SiebelPaymentClient)`)
- Overrides `__init__` to accept no arguments and skip the parent's HTTP/OAuth setup entirely
- Overrides every async method to return data from `data.py` — no HTTP calls
- Uses the method arguments (e.g. `profile_id`, `case_number`) to select the right persona's data where appropriate
- **Every method on the real client must be overridden.** Any method not yet given specific canned data should return a generic success dict (`{"status": "ok"}`) and log a warning: `mock_not_implemented method=X`. This prevents accidental real HTTP calls and makes gaps visible.
- Methods that return `bytes` (e.g. `get_report_pdf`, `get_t5007_pdf`) return a minimal valid PDF placeholder: `b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"` — enough to not crash PDF parsers but clearly fake.

### `data.py` — Canned response data

Organized by domain, keyed by persona identifiers so mock clients can look up the right response. All values are realistic BC income assistance data.

**Account responses:**
- `get_profile` → name, email, phone numbers, case number, case status
- `update_contact` → success response with updated fields echoed back
- `get_case_members` → dependants and spouse (Alice: 1 child; Bob: spouse + 2 children)
- `sync_profile` → success response
- `validate_pin` → success response
- `change_pin` / `request_pin_reset` / `confirm_pin_reset` → success responses

**Payment responses:**
- `get_payment_info` → upcoming benefit date, assistance type (EA), supplements, service provider payments
- `get_cheque_schedule` → 3 upcoming months with benefit_month, income_date, cheque_issue_date, period_close_date
- `get_t5007_slips` → slips for 2024 and 2025 with box_10/box_11 amounts
- `get_mis_data` → allowances (support=$760, shelter=$500, HSS=$50), deductions, AEE balance
- `get_t5_history_years` → list of available tax years [2024, 2025]
- `get_t5007_pdf` → dict with base64-encoded minimal PDF placeholder (this method uses `_get` and returns `dict`, not raw bytes)

**Notification responses:**
- `get_banners` → 2 banners (system maintenance notice, program update)
- `get_messages` → 5 messages: SD81 reminder (unread), form submission confirmation, general notice, SD81 restart notice (unread), older read message
- `get_message_detail` → full body text for each message
- `mark_read` / `send_message` / `delete_message` → success responses
- `sign_and_send` → success with signed_at timestamp

**Service Request responses:**
- `get_sr_list` → 3 SRs: ASSIST (Open), CRISIS_FOOD (Submitted), DIRECT_DEPOSIT (Cancelled)
- `get_sr_detail` → full detail with answers and attachment references
- `get_eligible_types` → filtered list based on case status
- `create_sr` → new SR with generated ID
- `cancel_sr` → success response with cancelled status
- `get_return_action` → return action metadata for the given SR type
- `finalize_sr_form` → success response

**Monthly Report responses:**
- `get_report_period` → current reporting window with dates
- `list_reports` → 3 reports: current month PARTIAL, last month SUBMITTED, 2 months ago RESUBMITTED
- `get_ia_questionnaire` → questionnaire form fields
- `start_report` → new report with generated SD81 ID
- `submit_monthly_report` → success with status=SUBMITTED
- `finalize` → success response
- `restart_report` → success with status=RESTARTED
- `get_summary` → summary of a finalized report
- `get_report_pdf` → minimal valid PDF bytes placeholder

**Employment Plan responses:**
- `get_ep_list` → 2 plans: one PENDING_SIGNATURE, one SUBMITTED
- `get_ep_detail` → full plan detail
- `sign_ep` / `send_to_icm` → success with signed_at timestamp
- `mark_form_submitted` → success response

**Registration responses:**
- `register_new_applicant` → success with SR number
- `register_existing_client` → success with portal linkage
- `get_link_options` → available link methods

**Admin responses:**
- `search_profiles` → returns Alice + Bob as results
- `get_client_profile` → full admin view of client
- `get_worker_permissions` → full access permissions
- `validate_ao_login` → success with applicant info

**Profile responses:**
- `get_tombstone` → full contact/address details
- `get_profile` → profile with case info
- `link_profile` → success
- `validate_pin` → success response
- `update_tombstone` → success with updated fields echoed back
- `has_newer_profile` → false
- `get_banners` → delegates to notification banners

**Attachment responses:**
- `upload_attachment` → success with attachment ID
- `get_attachment` → metadata for the attachment
- `delete_sr_attachment` → success response
- `get_message_attachment` / `get_sr_attachment` → metadata responses

### Injection mechanism

**Modified file:** `app/services/icm/deps.py`

Add `from app.config import get_settings` import. Refactor `_icm_kwargs()` to read from `get_settings()` instead of `os.environ` directly — this is consistent with the rest of the app and prevents `KeyError` if env vars are truly unset rather than empty.

Add a mapping from real client class to mock class:

```python
from app.config import get_settings

_MOCK_MAP: dict[type, type] = {}  # populated lazily

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
            return _clients[cls]
    # existing real-client logic unchanged
    if cls not in _clients:
        _clients[cls] = cls(**_icm_kwargs())
    return _clients[cls]
```

**Note:** Mock mode is determined by `get_settings()` which is `@lru_cache`-decorated — the decision is fixed at first call and cannot be toggled at runtime. This is intentional: mock mode is a development environment configuration, not a runtime switch.

**`clear_clients()` update:** Also clear `_MOCK_MAP` so test fixtures get a clean slate:

```python
def clear_clients() -> None:
    _clients.clear()
    _MOCK_MAP.clear()
```

### What does NOT change

- No router or service files are modified — they keep calling `get_siebel_client(SiebelPaymentClient)` etc.
- The 10 backward-compatible alias functions (`get_siebel_profile_client`, etc.) delegate to `get_siebel_client` and require no changes — mock injection is transparent.
- No new dependencies added to `pyproject.toml`
- No changes to test infrastructure — tests continue using respx/mocks as before

## Documentation Update

**Modified file:** `docs/onboarding/local-dev-setup.md`

New section **"Seed Data & Mock Mode"** inserted after "Run Alembic Migrations":

1. How to run the seeder (`python scripts/seed_db.py`)
2. What data gets created (persona table)
3. Mock ICM mode (auto-activates when `ENVIRONMENT=local` and `ICM_BASE_URL` is empty)
4. Using JWT tokens in Swagger UI
5. Resetting seed data (`--reset` flag)

## Out of scope

- Mock file storage (S3/PVC) — attachment records are created but no actual files on disk
- Mock Redis session data — admin session flows still need Redis running
- Mock email sending — registration verification emails are not simulated
- Performance testing data volumes — seed data is for functional dev/testing, not load testing
