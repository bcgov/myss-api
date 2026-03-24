# Modifying an Existing Dynamic Form

## When to use this guide

Use this guide when a form field needs to change: adding a new field, changing a label, adjusting validation rules, or modifying conditional visibility. Dynamic forms span both backend Pydantic schemas and SvelteKit frontend components.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- Familiarity with the [codebase overview](../onboarding/architecture.md)

---

## Steps

### 1. Identify the domain

Dynamic form definitions live in `myss-api/app/domains/`. Most form-bearing features have their own subdirectory:

```
myss-api/app/domains/
├── service_requests/   # SR forms (ASSIST, CRISIS_FOOD, DIET, etc.)
├── monthly_reports/    # Monthly report form
├── registration/       # Registration wizard
├── employment_plans/
└── notifications/
```

Open the relevant `models.py` to see the current field definitions.

---

### 2. Modify the Pydantic schema

All API request/response shapes are Pydantic `BaseModel` classes in the domain's `models.py`. This is the authoritative source for what the API accepts.

For the service requests dynamic form system, field definitions are expressed through `DynamicFormField` in `myss-api/app/domains/service_requests/models.py`:

```python
class DynamicFormField(BaseModel):
    field_id: str
    label: str
    field_type: str  # text, number, date, select, checkbox, textarea
    required: bool = False
    options: Optional[list[str]] = None
    validation: Optional[dict] = None
```

To add a new field to a form schema, locate where `DynamicFormPage` instances are constructed in `myss-api/app/domains/service_requests/service.py` (`get_form_schema` method) and add a new `DynamicFormField`:

```python
DynamicFormField(
    field_id="preferred_contact",
    label="Preferred Contact Method",
    field_type="select",
    required=True,
    options=["Phone", "Email", "Mail"],
)
```

To add cross-field validation, use Pydantic `@field_validator` on a request model:

```python
class SRSubmitRequest(BaseModel):
    pin: str
    spouse_pin: str | None = None
    declaration_accepted: bool

    @field_validator("declaration_accepted")
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Declaration must be accepted")
        return v
```

---

### 3. Update the SQLModel if the field is persisted

If the new field needs to be stored in the database (not just processed in memory), update the corresponding SQLModel in `myss-api/app/models/`. For service request drafts, that is `myss-api/app/models/service_requests.py`:

```python
class SRDraft(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    sr_type: str
    form_state_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    portal_status: str
    icm_sr_number: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

`form_state_json` is a JSON column. For most field changes, the answers dict stored in `form_state_json` handles arbitrary form data without a schema change. Only add a new column if you need indexed access or foreign key constraints on the new data.

---

### 4. Generate an Alembic migration if the schema changed

If you added or renamed a column in a SQLModel:

```bash
cd myss-api

# Auto-generate a migration
alembic revision --autogenerate -m "add_preferred_contact_to_sr_draft"

# Review the generated file in alembic/versions/ before applying
alembic upgrade head
```

Migration files are in `myss-api/alembic/versions/`. Follow the existing naming convention: `0005_sr_draft_table.py`, `0004_registration_tables.py`, etc.

If you only changed the Pydantic model (not the SQLModel), no migration is needed.

---

### 5. Update the SvelteKit form component

Frontend type definitions mirror the Pydantic models. Update `myss-web/src/lib/api/service-requests.ts` to reflect any field changes:

```typescript
// src/lib/api/service-requests.ts
export interface DynamicFormField {
    field_id: string;
    label: string;
    field_type: 'text' | 'number' | 'date' | 'select' | 'checkbox' | 'textarea';
    required: boolean;
    options?: string[] | null;
    validation?: Record<string, unknown> | null;
}
```

The form renderer in `myss-web/src/routes/service-requests/[id]/form/+page.svelte` reads `DynamicFormSchema` from the API and renders fields dynamically. If you added a new `field_type`, add the corresponding render branch in that component.

For non-dynamic form changes (fixed fields in registration, monthly reports), update the specific route component under `myss-web/src/routes/`.

---

### 6. Update validation rules

**Backend:** Pydantic validates on parse. Add validators to the request model as shown in Step 2. For conditional validation (field B required if field A has value X), use a `@model_validator`:

```python
from pydantic import model_validator

class MyRequest(BaseModel):
    has_spouse: bool
    spouse_pin: str | None = None

    @model_validator(mode="after")
    def spouse_pin_required_if_has_spouse(self) -> "MyRequest":
        if self.has_spouse and not self.spouse_pin:
            raise ValueError("spouse_pin required when has_spouse is True")
        return self
```

**Frontend:** Add client-side checks in the Svelte component before calling `updateFormDraft()`. This avoids unnecessary API round-trips.

---

### 7. Write or update tests

Test the changed schema in `myss-api/tests/`. See the [adding tests guide](./adding-tests.md) for patterns. At minimum:

- Unit test: the new field validates correctly (valid and invalid inputs)
- Unit test: the form schema returned by `get_form_schema()` includes the new field
- Integration test: `PUT /service-requests/{sr_id}/form` accepts and persists the new field

Example from `myss-api/tests/test_sr_create.py`:

```python
async def test_get_form_schema_returns_200(ac):
    token = make_token("CLIENT")
    response = await ac.get(
        "/service-requests/SR-NEW-001/form",
        params={"sr_type": "ASSIST"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    field = data["pages"][0]["fields"][0]
    assert field["field_id"] == "reason"
    assert field["field_type"] == "textarea"
    assert field["required"] is True
```

---

## Verification

1. Run backend tests: `cd myss-api && pytest tests/ -x`
2. Start the API and check the form schema endpoint: `GET /service-requests/{sr_id}/form?sr_type=ASSIST`
3. Confirm the new field appears in the `pages[0].fields` array of the response
4. Open the frontend and verify the field renders and submits without errors
5. If a migration was added: `alembic upgrade head` runs without error

---

## Common pitfalls

**Forgetting the migration.** If you add a column to a SQLModel but don't run `alembic revision --autogenerate`, the application will error at startup or on first write. Always check `alembic current` vs `alembic heads` after a model change.

**Pydantic vs SQLModel field mismatch.** `DynamicFormField` (Pydantic, in `domains/`) describes the form schema sent to the frontend. `SRDraft` (SQLModel, in `models/`) describes what is stored in the database. They serve different purposes and should be kept separately. Don't confuse changes to one as implying changes to the other.

**Stale TypeScript types.** If the Python schema changes but `myss-web/src/lib/api/service-requests.ts` is not updated, TypeScript will silently accept the old shape and the UI will display the wrong fields. Update the TS interface in the same PR as the Python change.

**`options` field is `null`, not `[]`.** The `DynamicFormField.options` type is `Optional[list[str]] = None`. Frontend code must handle `null` as "no options", not as an empty list.
