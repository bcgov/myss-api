# Development Guides

Step-by-step guides for common development tasks. Each guide follows a consistent format:

- **When to use this guide** — What triggers the need
- **Prerequisites** — What to read first
- **Steps** — Numbered, with file paths and code examples
- **Verification** — How to confirm it worked
- **Common pitfalls** — What goes wrong and how to avoid it

## Guides

### Forms & Service Requests
- [Updating Forms](updating-forms.md) — Modify an existing dynamic form (fields, validation, visibility)
- [Modifying a Service Request](modifying-service-request.md) — Change business logic of an existing SR type
- [Adding a Service Request](adding-service-request.md) — Add a new SR type end-to-end

### Features
- [Adding a Notification](adding-notification.md) — Add a new notification or message type
- [Adding an API Endpoint](adding-api-endpoint.md) — Add a new FastAPI route
- [Adding a Page](adding-page.md) — Add a new SvelteKit route/page
- [Adding a Celery Task](adding-celery-task.md) — Add an async background task

### Infrastructure
- [Adding Tests](adding-tests.md) — pytest, Vitest, and Playwright patterns
- [Adding a Database Migration](adding-database-migration.md) — SQLModel + Alembic workflow
- [Modifying Auth](modifying-auth.md) — Roles, permissions, and auth flow changes
- [Updating Siebel Integration](updating-siebel-integration.md) — ICM/Siebel REST API changes

## Updating dependencies

Dependencies are pinned via pip-tools. To update:

1. Edit `pyproject.toml` to change the version constraint.
2. Recompile the lock files:
   ```
   pip-compile --generate-hashes -o requirements.txt pyproject.toml
   pip-compile --generate-hashes --extra=dev -o requirements-dev.txt pyproject.toml
   ```
3. Commit `pyproject.toml`, `requirements.txt`, and `requirements-dev.txt` together.

Production installs should use `pip install -r requirements.txt` (no dev deps).
Development installs use `pip install -r requirements-dev.txt`.
