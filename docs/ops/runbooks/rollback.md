# Runbook: Rollback

## Context

This runbook covers rolling back the `myss-api` and/or `myss-frontend` deployments after a failed or problematic production release. Two options are provided. Option A is fastest (under 2 minutes); use Option B when Option A's previous revision is also bad or when you need to land a specific known-good image.

Before rolling back, check whether the current deployment includes a database migration. The correct procedure differs depending on whether the migration was additive or destructive.

---

## Migration Safety Assessment

Run this first. It takes 30 seconds and determines whether a database rollback is also required.

```bash
# What migration version is the database currently at?
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \
  "SELECT version_num, is_head FROM alembic_version;"

# What was the previous migration version?
# (Check alembic/versions/ in the repository for the down_revision of the current head)
```

| Migration type | DB rollback needed? |
|---|---|
| Additive only (new table, new column with default, new index) | No — old code works fine with extra columns/tables |
| Destructive (drop column, rename column, change type, remove table) | Yes — old code will fail if the column/table it expects is gone |

**If destructive migrations were applied, do not proceed with an app-only rollback without also running `alembic downgrade`. See the Destructive Migration section below.**

---

## Option A: `oc rollout undo` (fastest)

This reverts to the previous ReplicaSet in OpenShift history. It does not require knowing the previous image tag.

```bash
oc rollout undo deployment/myss-api -n ${NAMESPACE}
oc rollout undo deployment/myss-frontend -n ${NAMESPACE}
```

Monitor until complete:

```bash
oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
oc rollout status deployment/myss-frontend -n ${NAMESPACE} --timeout=5m
```

Note: `oc rollout undo` only goes back one revision by default. To go back further:

```bash
oc rollout history deployment/myss-api -n ${NAMESPACE}
oc rollout undo deployment/myss-api --to-revision=<N> -n ${NAMESPACE}
```

---

## Option B: Re-deploy a known-good image tag

Use this when you know the exact SHA of a previously working image.

```bash
export GOOD_TAG=<known-good-sha>
export GITHUB_ORG=bcgov
export NAMESPACE=myss-prod

oc set image deployment/myss-api \
  myss-api=ghcr.io/${GITHUB_ORG}/myss-api:${GOOD_TAG} \
  -n ${NAMESPACE}

oc set image deployment/myss-frontend \
  myss-frontend=ghcr.io/${GITHUB_ORG}/myss-frontend:${GOOD_TAG} \
  -n ${NAMESPACE}

oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
oc rollout status deployment/myss-frontend -n ${NAMESPACE} --timeout=5m
```

Note: The `alembic-migrate` init container will run again with the old image's migration code. If the database is already ahead of where the old code expects, the init container will attempt to downgrade — which will fail unless a `downgrade` migration exists. Handle this with the explicit `alembic downgrade` step below if needed.

---

## Destructive Migration Rollback

> **Warning:** Rolling back a destructive database migration risks data loss if rows have been written to new columns or new tables since the migration ran. Assess the situation with your DBA before proceeding.

### Step 1 — Identify the target downgrade revision

```bash
# In the repository
git log --oneline alembic/versions/
# Identify the revision immediately before the problematic migration
# It will be the down_revision value in the current head migration file
```

### Step 2 — Scale down the API to prevent new writes

```bash
oc scale deployment/myss-api --replicas=0 -n ${NAMESPACE}
```

### Step 3 — Run `alembic downgrade`

```bash
# Exec into the postgres pod and run downgrade via the API image
oc run alembic-downgrade \
  --image=ghcr.io/${GITHUB_ORG}/myss-api:${CURRENT_TAG} \
  --restart=Never \
  --env-from=secret/myss-db-secret \
  --env-from=configmap/myss-api-config \
  -n ${NAMESPACE} \
  -- alembic downgrade <target-revision>

# Watch for completion
oc logs -f alembic-downgrade -n ${NAMESPACE}
oc delete pod alembic-downgrade -n ${NAMESPACE}
```

### Step 4 — Deploy the known-good image

Proceed with Option B above. The init container will run `alembic upgrade head`, which is now a no-op (database is already at the correct revision for the old code).

### Step 5 — Scale back up

```bash
oc scale deployment/myss-api --replicas=2 -n ${NAMESPACE}
oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
```

---

## Verification

```bash
# Both deployments healthy
oc get deployment myss-api myss-frontend -n ${NAMESPACE}
# DESIRED  CURRENT  READY should all show 2

# Health endpoints
oc port-forward deployment/myss-api 8000:8000 -n ${NAMESPACE} &
curl -s http://localhost:8000/health

# Check logs for errors
oc logs -f deployment/myss-api -n ${NAMESPACE} --tail=50
```

---

## Post-Rollback Actions

1. File an incident report documenting: what failed, when, what was rolled back, and current status
2. Do not re-deploy the bad commit without a fix
3. If a migration was rolled back, coordinate with the team before the next deploy — migration version in the database must match the code being deployed
