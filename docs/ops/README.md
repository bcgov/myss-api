# Operations

## [Runbooks](runbooks/)

Day-to-day operational procedures:

- [Deploy to Test](runbooks/deploy-to-test.md) — Deploy a branch to a test environment
- [Promote to Production](runbooks/promote-to-prod.md) — Zero-downtime production deployment
- [Rollback](runbooks/rollback.md) — Revert a bad deployment
- [PVC Backup & Restore](runbooks/pvc-backup-restore.md) — PostgreSQL and Redis data management
- [Secrets Rotation](runbooks/secrets-rotation.md) — Rotate secrets via HashiCorp Vault
- [Troubleshooting](runbooks/troubleshooting.md) — Common issues and diagnosis

## [Environment Setup](setup/)

From-scratch provisioning guides for standing up a new environment:

- [OpenShift Project Setup](setup/openshift-project-setup.md) — Create and configure a new namespace
- [Vault Integration](setup/vault-integration.md) — Connect HashiCorp Vault to OpenShift
- [GitHub Actions Setup](setup/github-actions-setup.md) — CI/CD pipeline configuration
- [PVC Provisioning](setup/pvc-provisioning.md) — Persistent storage setup
- [Database Initialization](setup/database-initialization.md) — PostgreSQL first-time setup
