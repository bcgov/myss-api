# myss-api Documentation

Developer documentation for the MySelfServe API backend.

## Guides

Step-by-step guides for common development tasks. See [guides/README.md](guides/README.md).

**Backend-specific:**
- [Adding an API Endpoint](guides/adding-api-endpoint.md)
- [Adding a Celery Task](guides/adding-celery-task.md)
- [Adding a Database Migration](guides/adding-database-migration.md)
- [Updating Siebel Integration](guides/updating-siebel-integration.md)

**Cross-cutting (API + frontend coordination):**
- [Adding a Notification](guides/adding-notification.md)
- [Adding a Service Request](guides/adding-service-request.md)
- [Adding Tests](guides/adding-tests.md)
- [Modifying Auth](guides/modifying-auth.md)
- [Modifying a Service Request](guides/modifying-service-request.md)
- [Updating Forms](guides/updating-forms.md)

## Onboarding

- [Architecture Overview](onboarding/architecture.md)
- [Local Development Setup](onboarding/local-dev-setup.md)
- [Running Tests](onboarding/running-tests.md)

## Operations

- [Ops Index](ops/README.md)
- Runbooks: deploy, promote, rollback, troubleshoot, secrets rotation, PVC backup
- Setup: database init, GitHub Actions, OpenShift project, PVC provisioning, Vault

## Reference

- [Siebel/ICM Integration](reference/siebel-integration.md)
- [Legacy System Context](reference/legacy-system.md)
