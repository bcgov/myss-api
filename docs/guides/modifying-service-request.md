# Changing an Existing SR Type

## When to use this guide

Use this guide when the business logic, validation, or workflow of an existing service request type changes — for example, adding a new required field, changing how the form is structured, altering PDF generation behaviour, or modifying how the SR is finalized in Siebel.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)

---

## Steps

### 1. Find the SR type in the `SRType` enum

All SR types are defined as a string enum in `myss-api/app/domains/service_requests/models.py`:

```python
class SRType(str, Enum):
    ASSIST = "ASSIST"
    RREINSTATE = "RREINSTATE"
    CRISIS_FOOD = "CRISIS_FOOD"
    CRISIS_SHELTER = "CRISIS_SHELTER"
    CRISIS_CLOTHING = "CRISIS_CLOTHING"
    CRISIS_UTILITIES = "CRISIS_UTILITIES"
    CRISIS_MED_TRANSPORT = "CRISIS_MED_TRANSPORT"
    DIRECT_DEPOSIT = "DIRECT_DEPOSIT"
    DIET = "DIET"
    NATAL = "NATAL"
    MED_TRANSPORT_LOCAL = "MED_TRANSPORT_LOCAL"
    MED_TRANSPORT_NON_LOCAL = "MED_TRANSPORT_NON_LOCAL"
    RECONSIDERATION = "RECONSIDERATION"
    RECON_SUPPLEMENT = "RECON_SUPPLEMENT"
    RECON_EXTENSION = "RECON_EXTENSION"
    STREAMLINED = "STREAMLINED"
    BUS_PASS = "BUS_PASS"
    PWD_DESIGNATION = "PWD_DESIGNATION"
    PPMB = "PPMB"
```

Confirm the string value (e.g. `"DIET"`) matches what Siebel expects. The enum value is passed directly to Siebel in `SiebelSRClient.create_sr()`.

---

### 2. Understand what the type registry controls

`myss-api/app/domains/service_requests/sr_type_registry.py` classifies every SR type by two properties:

```python
class SRTypeRegistry:
    @staticmethod
    def is_dynamic(sr_type: SRType) -> bool:
        """True if the SR has a multi-page form. False = submit-only flow."""
        return sr_type in _DYNAMIC_TYPES

    @staticmethod
    def requires_pdf(sr_type: SRType) -> bool:
        """True if a PDF must be auto-generated at submit time."""
        return sr_type in _PDF_TYPES
```

**`_DYNAMIC_TYPES`** — the large set that includes `ASSIST`, `RREINSTATE`, `DIET`, `NATAL`, `RECONSIDERATION`, and most others. These display a form schema via `GET /service-requests/{sr_id}/form`.

**`_PDF_TYPES`** — a subset: `CRISIS_FOOD`, `CRISIS_SHELTER`, `CRISIS_CLOTHING`, `CRISIS_UTILITIES`, `CRISIS_MED_TRANSPORT`, `DIRECT_DEPOSIT`, `DIET`, `NATAL`. For these, `submit_sr()` calls `PDFGenerationService.generate()` before finalizing in Siebel.

If the change requires the SR to start or stop generating a PDF, or start or stop showing a dynamic form, update the appropriate set in `sr_type_registry.py`.

---

### 3. Modify domain logic in `service.py`

Business logic lives in `myss-api/app/domains/service_requests/service.py` inside `ServiceRequestService`. The key methods are:

| Method | Purpose |
|---|---|
| `create_sr()` | Creates SR in Siebel, inserts local `sr_drafts` row |
| `get_form_schema()` | Returns `DynamicFormSchema` for dynamic types; `None` for others |
| `save_form_draft()` | Updates `draft_json` in `sr_drafts` |
| `submit_sr()` | Validates PIN, generates PDF if needed, finalizes in Siebel, deletes draft |
| `get_sr_detail()` | Fetches SR detail from Siebel |
| `withdraw_sr()` | Cancels SR in Siebel |

When modifying an SR type's workflow, the most common change is in `get_form_schema()` (to add/remove fields) or `submit_sr()` (to change what happens at finalization). `get_form_schema()` currently returns a stub schema — the real implementation will load per-type schemas from DB or config.

---

### 4. Update Pydantic schemas if the request/response shape changes

Request and response models are in `myss-api/app/domains/service_requests/models.py`. If the SR submission now requires a new field:

```python
class SRSubmitRequest(BaseModel):
    pin: str
    spouse_pin: str | None = None
    declaration_accepted: bool
    # Add new field:
    special_circumstance: str | None = None
```

If the SR detail response needs to expose a new field, add it to `SRDetailResponse`. Pydantic will validate and serialize it automatically.

---

### 5. Update SvelteKit components

If the form shape, submit payload, or detail display changes, update:

- `myss-web/src/lib/api/service-requests.ts` — TypeScript interfaces (keep in sync with Python models)
- `myss-web/src/routes/service-requests/new/+page.svelte` — SR type selection
- `myss-web/src/routes/service-requests/[id]/form/+page.svelte` — form rendering
- `myss-web/src/routes/service-requests/[id]/submit/+page.svelte` — submission flow

The TypeScript `SRType` union in `service-requests.ts` must match the Python `SRType` enum exactly:

```typescript
export type SRType =
    | 'ASSIST'
    | 'RREINSTATE'
    | 'CRISIS_FOOD'
    // ... all 19 values
```

---

### 6. Update the Siebel client if ICM integration changes

The Siebel layer for SRs is `myss-api/app/services/icm/service_requests.py`:

```python
class SiebelSRClient(ICMClient):
    async def create_sr(self, sr_type: str, profile_id: str) -> dict:
        return await self._post("/service-requests", json={"sr_type": sr_type, "profile_id": profile_id})

    async def finalize_sr_form(self, sr_id: str, answers: dict) -> dict:
        return await self._post(f"/service-requests/{sr_id}/finalize", json={"answers": answers})
```

If Siebel introduces a new field required for a specific SR type at creation or finalization, update the relevant method. Use `self._get()`, `self._post()`, `self._put()`, or `self._delete()` — these are provided by `ICMClient` and include retry and circuit-breaker protection automatically.

If a new error code is introduced by Siebel for this SR type, add it to `myss-api/app/services/icm/error_mapping.py` and `myss-api/app/services/icm/exceptions.py`.

---

### 7. Update tests

Tests for SR logic are spread across several files:

- `myss-api/tests/test_sr_create.py` — create and draft endpoints
- `myss-api/tests/test_sr_submit.py` — submission logic
- `myss-api/tests/test_sr_list.py` — list endpoint
- `myss-api/tests/test_sr_status.py` — status checks
- `myss-api/tests/test_sr_type_registry.py` — registry classification
- `myss-api/tests/integration/test_sr_flow.py` — full lifecycle

At minimum, update the existing tests that cover the modified SR type and add new cases for the changed behaviour.

---

## Verification

1. `cd myss-api && pytest tests/test_sr_create.py tests/test_sr_submit.py tests/test_sr_type_registry.py tests/integration/test_sr_flow.py -x`
2. Confirm `SRTypeRegistry.is_dynamic()` and `requires_pdf()` return the expected values for the modified type
3. Start the API and exercise the full flow: create → save draft → submit
4. Check the Siebel mock (respx) captures the correct payload shape

---

## Common pitfalls

**Changing `_DYNAMIC_TYPES` or `_PDF_TYPES` without checking downstream effects.** Removing a type from `_DYNAMIC_TYPES` means `GET /service-requests/{sr_id}/form` returns 404 for that type. Clients that expect a form will break silently.

**`sr_type.value` vs `sr_type`.** `SiebelSRClient.create_sr()` receives `sr_type.value` (the raw string `"DIET"`, not the enum). Pass the `.value` when calling Siebel methods. Using the enum object directly will send `SRType.DIET` as the string representation, which Siebel will reject.

**Forgetting to update the TypeScript union.** The `SRType` type in `myss-web/src/lib/api/service-requests.ts` is a manually maintained union. It is not auto-generated from the Python enum. If the enum changes, update the TS file in the same PR.
