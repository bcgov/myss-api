# Runbook: Promote to Production

## Context

This runbook covers promoting a validated image from staging to the production OpenShift namespace with zero downtime. The API deployment uses a rolling update strategy (`maxUnavailable: 0`, `maxSurge: 1`) so at least 2 replicas are always serving traffic during the rollout.

The Alembic init container (`alembic-migrate`) runs `alembic upgrade head` before any new API pod begins accepting traffic. Migrations must therefore be backwards-compatible: the old pods are still running while the init container executes and new pods come up.

---

## Pre-Deployment Checklist

Complete every item before proceeding. Get sign-off in your team's change-management channel.

- [ ] All CI checks are green for the commit being promoted (check the `CI` workflow in GitHub Actions)
- [ ] The image has been running in staging/test for at least one business day without errors
- [ ] Smoke tests pass in the staging environment
- [ ] Any database migrations have been reviewed:
  - Additive-only migrations (new columns with defaults, new tables, new indexes) are safe to run during a rolling deploy
  - Destructive migrations (drop column, rename column, change type) require a multi-step deploy strategy — coordinate with the team before proceeding
- [ ] Stakeholder sign-off obtained and recorded
- [ ] On-call engineer is available for the next 30 minutes
- [ ] Rollback procedure reviewed: [rollback.md](./rollback.md)

---

## Rolling Update Strategy

Values from `openshift/api-deployment.yaml`:

```yaml
replicas: 2
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0   # never reduce below 2 healthy pods
    maxSurge: 1         # allow a temporary 3rd pod during rollout
```

What this means in practice:

1. OpenShift starts a 3rd pod (surge) with the new image
2. The `alembic-migrate` init container runs on that pod; all existing pods continue serving requests on the old code
3. Once migration completes and the new pod passes its readiness probe (`GET /health` on port 8000, must succeed within `failureThreshold: 3` × `periodSeconds: 10`), it enters the load balancer
4. One old pod is terminated
5. The process repeats for the second old pod
6. Total additional capacity held temporarily: 1 extra pod

The frontend deployment (`openshift/frontend-deployment.yaml`) uses the same `maxUnavailable: 0 / maxSurge: 1` strategy on port 3000.

---

## Steps

### Step 1 — Confirm the target SHA

```bash
export IMAGE_TAG=<full-git-sha>     # the SHA validated in staging
export GITHUB_ORG=bcgov             # adjust to actual org
export PROD_NAMESPACE=myss-prod     # production namespace
```

Verify the image exists in GHCR before proceeding:

```bash
# Confirm image is present (requires GHCR auth)
docker manifest inspect ghcr.io/${GITHUB_ORG}/myss-api:${IMAGE_TAG}
docker manifest inspect ghcr.io/${GITHUB_ORG}/myss-frontend:${IMAGE_TAG}
```

### Step 2 — Tag the image as production-ready (optional but recommended)

```bash
# Re-tag as prod-YYYY-MM-DD for traceability
PROD_TAG="prod-$(date +%Y-%m-%d)-${IMAGE_TAG:0:8}"
# Retag via GHCR or skopeo — exact command depends on your registry tooling
```

### Step 3 — Trigger the deployment

**Option A — via GitHub Actions:**

Re-run the `Deploy` workflow for the target commit from the GitHub Actions UI. Ensure the `production` environment is selected (it maps to `OPENSHIFT_NAMESPACE=myss-prod`).

**Option B — manual `oc` commands:**

```bash
oc set image deployment/myss-api \
  myss-api=ghcr.io/${GITHUB_ORG}/myss-api:${IMAGE_TAG} \
  -n ${PROD_NAMESPACE}

oc set image deployment/myss-frontend \
  myss-frontend=ghcr.io/${GITHUB_ORG}/myss-frontend:${IMAGE_TAG} \
  -n ${PROD_NAMESPACE}
```

### Step 4 — Monitor rollout

```bash
oc rollout status deployment/myss-api -n ${PROD_NAMESPACE} --timeout=10m
oc rollout status deployment/myss-frontend -n ${PROD_NAMESPACE} --timeout=10m
```

Watch init container completion and pod readiness:

```bash
oc get pods -n ${PROD_NAMESPACE} -l app=myss -w
```

Expect to see: `Init:0/1` → `PodInitializing` → `Running` for each new pod.

### Step 5 — Monitor Alembic init container

```bash
# Get the newest API pod
POD=$(oc get pods -n ${PROD_NAMESPACE} -l app=myss,component=api \
  --sort-by=.metadata.creationTimestamp -o name | tail -1)
oc logs ${POD} -c alembic-migrate -n ${PROD_NAMESPACE}
```

Expected output ends with: `INFO  [alembic.runtime.migration] Running upgrade ...` followed by `Done.`

If Alembic fails (exit non-zero), the pod will not start and no traffic is disrupted — existing pods remain healthy. See [rollback.md](./rollback.md).

### Step 6 — Smoke test production

```bash
# Health endpoints
curl -s https://myss.gov.bc.ca/health          # frontend (via Route)
oc port-forward deployment/myss-api 8000:8000 -n ${PROD_NAMESPACE} &
curl -s http://localhost:8000/health           # API direct
```

Manually verify at least one end-to-end flow (login → dashboard) in the production environment.

---

## Verification

```bash
# Confirm both deployments are on the correct image
oc get deployment myss-api myss-frontend -n ${PROD_NAMESPACE} \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[0].image}{"\n"}{end}'

# Confirm 2 replicas available for each
oc get deployment myss-api myss-frontend -n ${PROD_NAMESPACE}
# DESIRED  CURRENT  READY should all show 2
```

---

## Rollback

If anything looks wrong after deployment, follow [rollback.md](./rollback.md) immediately. Do not wait to gather more information — roll back first, then diagnose.
