# Runbook: Deploy to Test Environment

## Context

This runbook covers deploying a specific commit to a test OpenShift namespace. Two options are provided: triggering the GitHub Actions workflow (preferred) or running manual `oc` commands when you need to deploy a specific SHA without merging to `main`.

Images are published to `ghcr.io/<org>/myss-api` and `ghcr.io/<org>/myss-frontend` and tagged with both the full Git SHA and `latest`.

---

## Prerequisites

- `oc` CLI installed and authenticated to the target namespace
- The commit SHA you want to deploy has already been built and pushed to GHCR (check the `Build & Push Docker Images` job in GitHub Actions)
- You have `OPENSHIFT_NAMESPACE` set in your shell, or substitute it inline

```bash
export OPENSHIFT_NAMESPACE=myss-test1   # adjust for test environment
export GITHUB_ORG=bcgov                 # adjust to actual org
export IMAGE_TAG=<full-git-sha>         # 40-char SHA from git log
```

---

## Option A: GitHub Actions (preferred)

The `Deploy` workflow (`.github/workflows/deploy.yml`) triggers automatically on push to `main`. It:

1. Builds and pushes both images tagged with `$GITHUB_SHA` and `latest`
2. Calls `oc set image` for `deployment/myss-api` and `deployment/myss-frontend`
3. Waits up to 5 minutes for rollout to complete with `oc rollout status --timeout=5m`

To trigger for a specific SHA without a new merge, push a tag or manually re-run the workflow from the GitHub Actions UI (`Actions` → `Deploy` → `Run workflow`).

Required GitHub Actions secrets (set per environment in repo settings):

| Secret | Purpose |
|---|---|
| `OPENSHIFT_SERVER` | OpenShift API server URL |
| `OPENSHIFT_TOKEN` | Service account token for the namespace |
| `OPENSHIFT_NAMESPACE` | Target namespace (e.g. `myss-test1`) |

---

## Option B: Manual `oc` commands

Use this when you need to deploy a specific SHA directly without relying on the Actions runner.

### Step 1 — Update the API image

```bash
oc set image deployment/myss-api \
  myss-api=ghcr.io/${GITHUB_ORG}/myss-api:${IMAGE_TAG} \
  -n ${OPENSHIFT_NAMESPACE}
```

### Step 2 — Update the frontend image

```bash
oc set image deployment/myss-frontend \
  myss-frontend=ghcr.io/${GITHUB_ORG}/myss-frontend:${IMAGE_TAG} \
  -n ${OPENSHIFT_NAMESPACE}
```

### Step 3 — Monitor rollout

```bash
oc rollout status deployment/myss-api -n ${OPENSHIFT_NAMESPACE} --timeout=5m
oc rollout status deployment/myss-frontend -n ${OPENSHIFT_NAMESPACE} --timeout=5m
```

A successful rollout prints: `successfully rolled out`

If the timeout is exceeded, the command exits non-zero. Proceed to diagnosis (see Troubleshooting below).

---

## Verification

### Health check — API

The API exposes `GET /health` on port 8000. Identify the route or use port-forwarding:

```bash
# Port-forward for local verification
oc port-forward deployment/myss-api 8000:8000 -n ${OPENSHIFT_NAMESPACE} &
curl -s http://localhost:8000/health
# Expected: {"status": "ok"} or similar 200 response
```

### Health check — Frontend

The frontend exposes `GET /health` on port 3000:

```bash
oc port-forward deployment/myss-frontend 3000:3000 -n ${OPENSHIFT_NAMESPACE} &
curl -s http://localhost:3000/health
# Expected: 200 OK
```

### Confirm running image SHA

```bash
oc get deployment/myss-api -n ${OPENSHIFT_NAMESPACE} \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

oc get deployment/myss-frontend -n ${OPENSHIFT_NAMESPACE} \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Both should show your `${IMAGE_TAG}`.

### Tail logs

```bash
# API logs
oc logs -f deployment/myss-api -n ${OPENSHIFT_NAMESPACE}

# Frontend logs
oc logs -f deployment/myss-frontend -n ${OPENSHIFT_NAMESPACE}

# Alembic init container logs (most recent pod)
POD=$(oc get pods -n ${OPENSHIFT_NAMESPACE} -l app=myss,component=api \
  --sort-by=.metadata.creationTimestamp -o name | tail -1)
oc logs ${POD} -c alembic-migrate -n ${OPENSHIFT_NAMESPACE}
```

---

## Rollback

If the deployment is unhealthy, see [rollback.md](./rollback.md).
