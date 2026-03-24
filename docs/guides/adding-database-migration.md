# Adding a Database Migration

## When to use this guide

Use this guide whenever the database schema needs to change: adding a new table, adding a column to an existing table, changing a column type, adding an index, or any other DDL change.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)
- PostgreSQL running locally (or SQLite for fast iteration — see `alembic.ini`)

---

## Steps

### 1. Modify or create a SQLModel in `app/models/`

All database tables are defined as SQLModel classes with `table=True`. The `User` and `Profile` models in `myss-api/app/models/user.py` show the conventions:

```python
from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    bceid_guid: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Profile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    portal_id: str = Field(unique=True, index=True)
    link_code: str
    mis_person_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Conventions to follow:

- Primary keys: `UUID` with `default_factory=uuid4`
- Timestamps: `datetime` with `default_factory=lambda: datetime.now(UTC)` — always timezone-aware
- Foreign keys: `Field(foreign_key="tablename.column")` using the SQLModel table name (lowercase class name by default)
- Indexes: `Field(index=True)` for columns used in WHERE clauses; `Field(unique=True, index=True)` for unique lookup columns

**To add a column to an existing model:**

```python
class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    bceid_guid: str = Field(unique=True, index=True)
    display_name: str | None = None  # ← new nullable column
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Use `str | None = None` (nullable) for new columns on existing tables so that rows inserted before this migration remain valid.

**To create a new table:**

```python
class YourNewTable(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    some_field: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### 2. Ensure the model is imported in `app/models/__init__.py`

Alembic discovers all tables by importing `app.models` in `myss-api/alembic/env.py`:

```python
# alembic/env.py
import app.models  # noqa: F401
```

This line triggers `app/models/__init__.py`, which must explicitly import every model class. The current `__init__.py`:

```python
from .user import User, Profile
from .registration import RegistrationSession
from .ao_registration import AORegistrationSession
from .service_requests import SRDraft
from .attachments import AttachmentRecord, ScanJob
from .employment import PlanSignatureSession
from .auth_tokens import PINResetToken
from .audit import WorkerAuditRecord
from .misc import DisclaimerAcknowledgement
```

If you created a new model file, add its import here. If you added a class to an existing file, add the class name to that file's import line:

```python
from .user import User, Profile, YourNewTable  # ← add new class
```

If you skip this step, Alembic will not see the new table and `--autogenerate` will produce an empty migration.

### 3. Generate the migration

```bash
cd myss-api

# Autogenerate compares the current schema against SQLModel metadata
alembic revision --autogenerate -m "add display_name to user"
```

This creates a new file in `myss-api/alembic/versions/` with auto-generated `upgrade()` and `downgrade()` functions.

### 4. Review the generated migration

**Always open the generated file and read it before running it.** Autogenerate is a starting point, not a final answer.

Common things to check and fix:

- **Nullable vs NOT NULL**: Verify that new columns on existing tables are nullable (`nullable=True`) to avoid failures on existing rows.
- **Server defaults**: If a non-nullable column is added to a populated table, you need `server_default="some_value"` in the migration even if the model has a Python default.
- **Enum types**: SQLAlchemy/Alembic often misses `Enum` type creation or uses the wrong dialect. Verify enum handling for your target database (PostgreSQL enums need `CREATE TYPE`).
- **Index names**: Autogenerate sometimes produces duplicate or overly long index names. Review and shorten if needed.
- **Empty migration**: If the file has empty `upgrade()` / `downgrade()` functions, the model was not imported. Go back to step 2.

Example of what a well-formed generated migration looks like:

```python
def upgrade() -> None:
    op.add_column('user', sa.Column('display_name', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('user', 'display_name')
```

### 5. Run the migration locally

```bash
cd myss-api

# Apply all pending migrations
alembic upgrade head

# Verify the migration ran
alembic current
```

The database URL is taken from `alembic.ini` (defaults to `sqlite+aiosqlite:///./test.db`). For local PostgreSQL, set `DATABASE_URL` in your environment and ensure `alembic/env.py` picks it up, or override in `alembic.ini`.

### 6. Test the rollback

Before committing, verify the downgrade works:

```bash
# Roll back one migration
alembic downgrade -1

# Confirm the column/table is gone, then re-apply
alembic upgrade head
```

A migration that cannot be rolled back will block incident recovery in production.

### 7. Run the test suite

```bash
cd myss-api
make test
```

The test suite creates the schema from scratch using `SQLModel.metadata.create_all()`. If the tests pass after your change, the schema is consistent.

---

## OpenShift deployment note

The `openshift/api-deployment.yaml` defines an init container that runs before the API starts:

```yaml
initContainers:
  - name: alembic-migrate
    image: myss-api:latest
    command: ["alembic", "upgrade", "head"]
    envFrom:
      - secretRef:
          name: myss-db-secret
      - configMapRef:
          name: myss-api-config
```

This means migrations run automatically on every deployment. During a rolling update, the new code and the old code run simultaneously while the migration is in progress.

**Migrations must be backwards-compatible.** The running old-code API pods must be able to function against the new schema while the rollout completes. The safe patterns are:

- Adding a nullable column (old code ignores it)
- Adding a new table (old code ignores it)
- Adding an index (transparent to application code)

Unsafe patterns that require a multi-step deployment:

- Renaming a column (breaks old code immediately) — add a new column, migrate data, remove the old column in a later deployment
- Dropping a column that old code still reads
- Making a nullable column non-nullable on a live table

---

## Common pitfalls

**Autogenerate produces an empty migration**
The model was not imported in `app/models/__init__.py`. Add the import and re-run `alembic revision --autogenerate`.

**Autogenerate misses enum types**
SQLAlchemy's autogenerate does not always detect custom enum changes. If you add or modify a Python `Enum` used as a column type, manually add the `CREATE TYPE` / `ALTER TYPE` DDL to the migration.

**Non-reversible migrations**
A migration with an empty `downgrade()` will block rollback during an incident. Even if rollback is unlikely, implement it — `op.drop_column` / `op.drop_table` for things added in `upgrade()`.

**Forgetting `__init__.py` after creating a new model file**
New files are not auto-imported. Every new model file needs a corresponding import in `app/models/__init__.py` or Alembic will not see the table.

**Running `alembic upgrade head` against the wrong database**
Check `alembic current` first to confirm which database is being targeted. The `DATABASE_URL` environment variable overrides `alembic.ini`.
