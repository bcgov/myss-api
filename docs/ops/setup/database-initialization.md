# Database Initialization

**Audience:** Platform/ops engineer or senior developer.
**Read time:** ~20 minutes.
**When to use:** New environment provisioning. Run after secrets are in place and PVCs are provisioned.

---

## Prerequisites

- OpenShift project `myss-<env>` exists (see [openshift-project-setup.md](./openshift-project-setup.md))
- All secrets created in the namespace (see [vault-integration.md](./vault-integration.md)):
  - `myss-db-secret` with keys `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- PVCs provisioned (see [pvc-provisioning.md](./pvc-provisioning.md)):
  - `myss-postgres-pvc` (10 Gi) exists
- `oc` CLI access to the target namespace

---

## 1. Deploy PostgreSQL

Apply the PostgreSQL manifest. This creates the Deployment, the PVC (if not pre-created),
and the ClusterIP Service in one step.

```bash
ENV=dev1   # set for your environment

oc apply -f openshift/postgres-deployment.yaml -n myss-${ENV}
```

Wait for the pod to become ready:

```bash
oc rollout status deployment/myss-postgres -n myss-${ENV} --timeout=3m
```

---

## 2. Verify the PostgreSQL Pod and PVC

Check that the pod is running and the PVC is bound:

```bash
oc get pods -l app=myss,component=postgres -n myss-${ENV}
# Expected: STATUS = Running

oc get pvc myss-postgres-pvc -n myss-${ENV}
# Expected: STATUS = Bound
```

Confirm PostgreSQL is accepting connections from inside the cluster:

```bash
oc exec deployment/myss-postgres -n myss-${ENV} -- \
  psql -U $(oc get secret myss-db-secret -n myss-${ENV} \
    -o jsonpath='{.data.POSTGRES_USER}' | base64 -d) \
  -c "\conninfo"
```

Expected output includes: `You are connected to database "myss" as user "myss"`.

---

## 3. Run Initial Alembic Migrations

Alembic is configured in `myss-api/alembic/env.py`. It uses an async SQLAlchemy
engine (`create_async_engine`) with the `DATABASE_URL` from `myss-db-secret`.
The migration target is `SQLModel.metadata`, which covers all models imported via
`app.models`.

In normal deploys, migrations run automatically as an init container in `myss-api`.
For the initial provisioning, use one of the two methods below.

### Method A: Standalone Alembic Job (recommended)

The manifest `openshift/alembic-job.yaml` runs `alembic upgrade head` as a
one-shot Job. It uses the same `myss-db-secret` and `myss-api-config` as the API.

```bash
oc apply -f openshift/alembic-job.yaml -n myss-${ENV}
```

Wait for the job to complete:

```bash
oc wait job/myss-alembic-migrate \
  --for=condition=complete \
  --timeout=3m \
  -n myss-${ENV}
```

Check logs to confirm success:

```bash
oc logs job/myss-alembic-migrate -n myss-${ENV}
# Expected last line: "INFO  [alembic.runtime.migration] Running upgrade ..."
# or "INFO  [alembic.runtime.migration] No new revisions to apply."
```

Clean up the completed job after confirming success:

```bash
oc delete job myss-alembic-migrate -n myss-${ENV}
```

### Method B: oc exec into a Running API Pod

If the API is already deployed (e.g. for a re-migration), run Alembic directly
inside an existing pod:

```bash
oc exec deployment/myss-api -n myss-${ENV} -- alembic upgrade head
```

---

## 4. Seed Reference Data

### Reference data seeding

A seed script populates the local database with three test personas
(Alice, Bob, Carol) and a worker persona, plus rate tables used by the
eligibility estimator.

Run it after `alembic upgrade head`:

    python scripts/seed_db.py

The script prints JWT tokens for each persona to stdout — copy these
into the frontend `.env` file (`MOCK_AUTH_TOKEN_ALICE`, etc.) for local
development without real BCeID login.

Seed data is idempotent for registration sessions and eligibility rate
tables, but re-running will issue fresh JWTs and case numbers. For a
clean local state, delete `dev.db` (SQLite) and re-run
`alembic upgrade head` + `seed_db.py`.

---

## 5. Verify API → Database Connectivity

Deploy the API (if not already deployed):

```bash
oc apply -f openshift/api-deployment.yaml -n myss-${ENV}
oc rollout status deployment/myss-api -n myss-${ENV} --timeout=5m
```

The API init container runs `alembic upgrade head` on every deploy. If it fails,
the main container does not start. A successful rollout confirms database connectivity.

Additionally, check the health endpoint from inside the cluster:

```bash
oc exec deployment/myss-api -n myss-${ENV} -- \
  curl -sf http://localhost:8000/health
```

Expected: `{"status":"ok"}` or equivalent.

Check API logs for any database connection errors:

```bash
oc logs deployment/myss-api -n myss-${ENV} --tail=50
```

Look for errors containing `asyncpg`, `sqlalchemy`, or `could not connect`. If present,
verify `DATABASE_URL` in `myss-db-secret` matches the PostgreSQL service hostname
(`myss-postgres`) and credentials.

---

## 6. Alembic Migration Management

### Check current migration state

```bash
oc exec deployment/myss-api -n myss-${ENV} -- alembic current
```

### Show migration history

```bash
oc exec deployment/myss-api -n myss-${ENV} -- alembic history --verbose
```

### Roll back one revision (use with caution)

```bash
oc exec deployment/myss-api -n myss-${ENV} -- alembic downgrade -1
```

Rolling back in production requires coordinating with the team — the data changes
may not be reversible.

---

## 7. Configuration Reference

Key values from `openshift/configmap.yaml` that affect the database:

| ConfigMap key | Default value | Purpose |
|---|---|---|
| `REDIS_SESSION_TTL_SECONDS` | `900` | Session expiry (15 min) |
| `ICM_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before breaker opens |
| `ICM_BASE_URL` | `https://icm.gov.bc.ca/siebel/v1.0` | Siebel REST endpoint |

The `DATABASE_URL` in `myss-db-secret` must use the `postgresql+asyncpg://` scheme
because `alembic/env.py` uses `create_async_engine`. The standard `postgresql://`
scheme will cause a connection error.

---

## Next Steps

- **[GitHub Actions setup](./github-actions-setup.md)** — configure CI/CD so future migrations run automatically on deploy
- **Backup setup** — schedule PostgreSQL dumps before going live: `docs/ops/runbooks/pvc-backup-restore.md`
- **Deploy Redis and Celery**:
  ```bash
  oc apply -f openshift/redis-deployment.yaml -n myss-${ENV}
  oc apply -f openshift/celery-deployment.yaml -n myss-${ENV}
  ```

> Frontend deployment is owned by the `myss-web` repository. This
> runbook only covers the API and its PostgreSQL database.
