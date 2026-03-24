# Adding a New SR Type End-to-End

## When to use this guide

Use this guide when a new service request type is being introduced — for example, a new benefit, supplement, or program that requires a dedicated SR type in both the portal and Siebel.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)
- Read the [modifying an existing SR type guide](./modifying-service-request.md) first — it explains the data model

---

## Steps

### 1. Add the new type to the `SRType` enum

In `myss-api/app/domains/service_requests/models.py`, add the new type to `SRType`:

```python
class SRType(str, Enum):
    ASSIST = "ASSIST"
    # ... existing types ...
    PPMB = "PPMB"
    # Add your new type:
    WELLNESS_SUPPLEMENT = "WELLNESS_SUPPLEMENT"
```

The string value (`"WELLNESS_SUPPLEMENT"`) is passed directly to Siebel. Confirm the exact string expected by the Siebel API before committing.

---

### 2. Register in the type registry

In `myss-api/app/domains/service_requests/sr_type_registry.py`, decide which sets the new type belongs to:

**Add to `_DYNAMIC_TYPES`** if the SR has a multi-page form (the user fills in fields before submitting):

```python
_DYNAMIC_TYPES: set[SRType] = {
    SRType.ASSIST,
    # ... existing ...
    SRType.WELLNESS_SUPPLEMENT,   # <-- add here if it has a form
}
```

**Add to `_PDF_TYPES`** if a PDF must be auto-generated at submit time:

```python
_PDF_TYPES: set[SRType] = {
    SRType.CRISIS_FOOD,
    # ... existing ...
    SRType.WELLNESS_SUPPLEMENT,   # <-- add here if PDF required
}
```

SR types in neither set follow a simple submit-only flow: `POST /service-requests` creates the SR, and `POST /service-requests/{sr_id}/submit` finalizes it with no form pages. `BUS_PASS` is an example of this pattern.

---

### 3. Create Pydantic models for the new SR's specific fields

If the new type has unique fields not covered by the generic `SRFormUpdateRequest` / `SRSubmitRequest`, add them in `myss-api/app/domains/service_requests/models.py`. For most SRs the existing models are sufficient because form answers are stored as a free-form `dict` in `draft_json`.

If the new SR type requires validated, typed submission data (e.g. a bank account number for a direct deposit variant), add a dedicated request model:

```python
class WellnessSupplementSubmitRequest(SRSubmitRequest):
    wellness_reason: str
    medical_practitioner_name: str
```

Then handle this in the router or service layer.

---

### 4. Add domain logic in `service.py`

In `myss-api/app/domains/service_requests/service.py`, add the form schema definition for the new dynamic type inside `get_form_schema()`:

```python
async def get_form_schema(self, sr_id: str, sr_type: SRType) -> Optional[DynamicFormSchema]:
    if not SRTypeRegistry.is_dynamic(sr_type):
        return None

    if sr_type == SRType.WELLNESS_SUPPLEMENT:
        return DynamicFormSchema(
            form_type=DynamicFormType.SR,
            sr_type=sr_type,
            pages=[
                DynamicFormPage(
                    page_index=0,
                    title="Wellness Information",
                    fields=[
                        DynamicFormField(
                            field_id="wellness_reason",
                            label="Reason for Request",
                            field_type="textarea",
                            required=True,
                        ),
                        DynamicFormField(
                            field_id="medical_practitioner_name",
                            label="Medical Practitioner Name",
                            field_type="text",
                            required=True,
                        ),
                    ],
                )
            ],
            total_pages=1,
        )

    # Existing stub schema for other types
    return DynamicFormSchema(...)
```

No changes to `create_sr()`, `save_form_draft()`, or `submit_sr()` are typically needed — they work generically across all types via the registry.

---

### 5. Add Siebel integration if the new type requires new API calls

The Siebel SR client is in `myss-api/app/services/icm/service_requests.py`. The existing methods handle all current types generically. If the new SR type requires a Siebel-side operation that does not exist yet (e.g. a new finalization endpoint), add a method:

```python
class SiebelSRClient(ICMClient):
    # existing methods ...

    async def finalize_wellness_sr(self, sr_id: str, practitioner_data: dict) -> dict:
        return await self._post(
            f"/service-requests/{sr_id}/finalize-wellness",
            json=practitioner_data,
        )
```

Use `self._post()`, `self._get()`, etc. All inherit retry (3 attempts, exponential backoff) and circuit breaker (5 failures, 30s recovery) from `ICMClient`.

If Siebel returns new error codes specific to this type, register them in `myss-api/app/services/icm/error_mapping.py` and add a corresponding exception class in `myss-api/app/services/icm/exceptions.py`.

---

### 6. Confirm the existing router handles the new type

No router changes are required. `myss-api/app/routers/service_requests.py` is fully generic — it dispatches to `ServiceRequestService` for all SR types. The registry pattern handles type-specific branching inside the service layer.

Verify by inspecting the create endpoint:

```python
@router.post("", response_model=SRDraftResponse, status_code=201)
async def create_service_request(
    request: SRCreateRequest,          # SRCreateRequest.sr_type is a SRType enum
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: ServiceRequestService = Depends(_get_sr_service),
) -> SRDraftResponse:
    return await svc.create_sr(
        sr_type=request.sr_type,       # new enum value flows through automatically
        profile_id=user.user_id,
        user_id=user.user_id,
    )
```

FastAPI validates `request.sr_type` against the `SRType` enum. As soon as you add the new value to the enum, it becomes a valid API input with no router changes.

---

### 7. Create the SvelteKit route

Create a form page for the new SR type. The pattern follows `myss-web/src/routes/service-requests/[id]/form/+page.svelte`, which reads the form schema from the API and renders fields dynamically. If the new type has a standard multi-page form, no new route is needed — the existing dynamic form renderer handles it.

If the new type needs a custom UI (e.g. a specialized layout not supported by generic field rendering), create a dedicated route:

```
myss-web/src/routes/service-requests/wellness/
└── +page.svelte
```

---

### 8. Add the new type to the frontend API client

In `myss-web/src/lib/api/service-requests.ts`, add the new type to the `SRType` union:

```typescript
export type SRType =
    | 'ASSIST'
    | 'RREINSTATE'
    // ... existing ...
    | 'PPMB'
    | 'WELLNESS_SUPPLEMENT';   // <-- add here
```

This is a manually maintained union — it is not auto-generated from the Python enum. The TS type and Python enum must stay in sync.

If the new type has a dedicated API function (e.g. a custom submit call), add it to `service-requests.ts` following the existing `apiPost` / `apiGet` helper pattern.

---

### 9. Add a database migration if needed

The `sr_drafts` table (defined in `myss-api/app/models/service_requests.py`) stores `sr_type` as a plain `str` column, so adding a new enum value does not require a migration. The new value is accepted without a schema change.

A migration is only required if you add a new column to a SQLModel. In that case:

```bash
cd myss-api
alembic revision --autogenerate -m "add_wellness_supplement_field"
# Review the generated file in alembic/versions/ before applying
alembic upgrade head
```

---

### 10. Write full test coverage

Add tests for the new type at every layer. Mirror the file structure of an existing SR type.

**Unit tests** — verify `SRTypeRegistry` classifies the new type correctly:

```python
# myss-api/tests/test_sr_type_registry.py
def test_wellness_supplement_is_dynamic():
    assert SRTypeRegistry.is_dynamic(SRType.WELLNESS_SUPPLEMENT) is True

def test_wellness_supplement_requires_pdf():
    assert SRTypeRegistry.requires_pdf(SRType.WELLNESS_SUPPLEMENT) is False
```

**Route tests** — verify the create endpoint accepts the new type:

```python
# myss-api/tests/test_sr_create.py
async def test_create_wellness_supplement_returns_201(ac):
    token = make_token("CLIENT")
    response = await ac.post(
        "/service-requests",
        json={"sr_type": "WELLNESS_SUPPLEMENT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
```

**Integration test** — exercise the full lifecycle using `myss-api/tests/integration/test_sr_flow.py` as a template. Mock `SiebelSRClient` at the boundary, run the real `ServiceRequestService`.

---

## Verification

1. `cd myss-api && pytest tests/ -x -k "wellness"` passes
2. `pytest tests/test_sr_type_registry.py -x` confirms registry classification
3. `POST /service-requests` with `{"sr_type": "WELLNESS_SUPPLEMENT"}` returns `201`
4. `GET /service-requests/{sr_id}/form?sr_type=WELLNESS_SUPPLEMENT` returns the form schema if dynamic
5. Full submit flow completes without errors

---

## Common pitfalls

**String mismatch with Siebel.** The enum value string (e.g. `"WELLNESS_SUPPLEMENT"`) is sent directly to Siebel as the SR type identifier. If Siebel expects a different casing or format (e.g. `"WellnessSupplement"`), align the enum value with what Siebel accepts, or add a mapping in `SiebelSRClient.create_sr()`.

**Forgetting to update both `_DYNAMIC_TYPES` and frontend `SRType`.** The registry classifies the type; the TS union declares it to the frontend. Missing either causes silent failures — the API returns 422 for unknown type values, and the TS compiler may allow invalid values if the union is not updated.

**`BUS_PASS` is not in `_DYNAMIC_TYPES`.** If your new SR is submit-only (no form), intentionally omit it from `_DYNAMIC_TYPES`. `GET /service-requests/{sr_id}/form` will correctly return 404. This is expected behaviour, not a bug.
