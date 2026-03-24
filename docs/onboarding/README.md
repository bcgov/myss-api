# Onboarding — Start Here

Welcome to MySS 2.0. Read these in order:

1. **[Architecture Overview](architecture.md)** — System components, domain mapping, request lifecycle, key decisions
2. **[Local Dev Setup](local-dev-setup.md)** — Get a working development environment
3. **[Running Tests](running-tests.md)** — Test infrastructure, commands, and patterns

## What is MySS 2.0?

MySS (MySelfServe) is the BC Government's self-service portal for income assistance clients. It allows clients to:

- Apply for and manage service requests (19 types including bus passes, crisis supplements, diet allowances)
- Submit and track monthly reports
- View payment information and cheque schedules
- Manage their account, PIN, and contact information
- Receive notifications and messages from their ministry worker

Ministry workers (admin users) can also use the system to view client data and perform operations on their behalf.

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | SvelteKit 2.x (TypeScript, Svelte 5) |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 (SQLModel ORM) |
| Cache / Sessions | Redis 7 |
| Task Queue | Celery |
| Auth | Auth.js + Keycloak/OIDC (BCeID, BC Services Card, IDIR) |
| Migrations | Alembic |
| Platform | OpenShift 4.x |
| CI/CD | GitHub Actions → ghcr.io → OpenShift |
