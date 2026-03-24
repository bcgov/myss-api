# Runbook: Secrets Rotation

## Context

This runbook covers rotating credentials for all OpenShift secrets used by the MySS 2.0 application. Secrets are defined as templates in `openshift/secrets-template.yaml`. The actual values must never be committed to source control.

After any rotation, the affected workloads must be restarted to pick up the new values (OpenShift does not automatically restart pods when a secret changes).

---

## Secrets Inventory

| Secret name | Key(s) | Used by | Rotation trigger |
|---|---|---|---|
| `myss-db-secret` | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `myss-api` (app + init container), `myss-postgres` pod | Password compromise, scheduled rotation, DBA request |
| `myss-redis-secret` | `REDIS_URL`, `REDIS_PASSWORD` | `myss-api`, `myss-celery`, `myss-redis` pod | Password compromise, scheduled rotation |
| `myss-icm-secret` | `ICM_CLIENT_ID`, `ICM_CLIENT_SECRET`, `ICM_TOKEN_URL` | `myss-api` | Siebel team rotation, credential compromise |
| `myss-auth-secret` | `AUTH_SECRET`, `AUTH_TRUST_HOST` | `myss-frontend` | JWT signing key rotation, compromise |
| `myss-mail-secret` | `MAILJET_API_KEY`, `MAILJET_API_SECRET` | `myss-api` | MailJet credential compromise, scheduled rotation |

---

## Vault Integration (To Be Confirmed)

The current deployment uses manually managed OpenShift secrets. A future state using one of the following patterns is under evaluation:

- **Vault Agent sidecar**: Vault injects secrets as files; app reads from filesystem
- **external-secrets operator**: An `ExternalSecret` CR syncs from Vault to an OpenShift Secret automatically
- **Manual sync**: Operator rotates in Vault, then runs `oc create secret generic --dry-run=client -o yaml | oc apply -f -`

Until Vault integration is confirmed, follow the manual rotation procedure below.

---

## General Rotation Procedure

For each secret:

### Step 1 — Generate the new credential

Generate a new value outside OpenShift (password manager, `openssl rand -hex 32`, provider console, etc.).

### Step 2 — Update the secret in OpenShift

```bash
NAMESPACE=myss-prod

# Example: rotate a single key in myss-db-secret
oc patch secret myss-db-secret \
  -n ${NAMESPACE} \
  --type=merge \
  -p "{\"stringData\":{\"POSTGRES_PASSWORD\":\"<new-password>\"}}"
```

For a full secret replacement:

```bash
oc create secret generic myss-db-secret \
  --from-literal=DATABASE_URL="postgresql://<user>:<new-password>@myss-postgres:5432/<db>" \
  --from-literal=POSTGRES_USER="<user>" \
  --from-literal=POSTGRES_PASSWORD="<new-password>" \
  --from-literal=POSTGRES_DB="<db>" \
  --dry-run=client -o yaml | oc apply -f - -n ${NAMESPACE}
```

### Step 3 — Update the credential at the source

For `POSTGRES_PASSWORD`: update the password inside PostgreSQL before restarting pods.

```bash
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${OLD_USER} --dbname=postgres -c \
  "ALTER USER ${POSTGRES_USER} WITH PASSWORD '<new-password>';"
```

For `REDIS_PASSWORD`: the password is passed as a startup argument to the Redis container. After updating the secret, restart the Redis deployment — it will pick up the new `REDIS_PASSWORD` env var on the next pod start.

For `ICM_CLIENT_SECRET` / `MAILJET_API_SECRET`: rotate in the provider's console first, then update the OpenShift secret.

### Step 4 — Rolling restart of affected workloads

```bash
# myss-db-secret affects: myss-api (and its init container), myss-postgres
oc rollout restart deployment/myss-api -n ${NAMESPACE}
oc rollout restart deployment/myss-postgres -n ${NAMESPACE}  # only if DB user/password changed

# myss-redis-secret affects: myss-api, myss-celery, myss-redis
oc rollout restart deployment/myss-api -n ${NAMESPACE}
oc rollout restart deployment/myss-celery -n ${NAMESPACE}
oc rollout restart deployment/myss-redis -n ${NAMESPACE}

# myss-icm-secret affects: myss-api only
oc rollout restart deployment/myss-api -n ${NAMESPACE}

# myss-auth-secret affects: myss-frontend only
oc rollout restart deployment/myss-frontend -n ${NAMESPACE}

# myss-mail-secret affects: myss-api only
oc rollout restart deployment/myss-api -n ${NAMESPACE}
```

Monitor rollout completion:

```bash
oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
```

### Step 5 — Verify

```bash
# API health (confirms DB + Redis connectivity)
oc port-forward deployment/myss-api 8000:8000 -n ${NAMESPACE} &
curl -s http://localhost:8000/health

# Check logs for authentication errors
oc logs -f deployment/myss-api -n ${NAMESPACE} --tail=50
```

---

## `AUTH_SECRET` (JWT Signing Key) — Special Handling

The `AUTH_SECRET` in `myss-auth-secret` is used by Auth.js to sign session JWTs. Rotating it invalidates all existing sessions immediately — every logged-in user will be signed out.

### Overlap period procedure

If graceful logout is required (e.g., during business hours):

1. Schedule the rotation during a maintenance window or low-traffic period (evening/weekend)
2. Notify users via a banner (using the existing banner notification mechanism) that a brief session interruption will occur at a specific time
3. At the maintenance window: update `AUTH_SECRET` and restart `myss-frontend`
4. All existing sessions will fail validation on the next API call; users are redirected to the login page

There is no multi-key overlap support in Auth.js v5 by default. If zero-disruption JWT rotation is required, it must be implemented at the application level (supporting both old and new signing keys for a transition window). Raise this as a product requirement if needed.

```bash
# Generate a new AUTH_SECRET
NEW_SECRET=$(openssl rand -hex 32)

oc patch secret myss-auth-secret \
  -n ${NAMESPACE} \
  --type=merge \
  -p "{\"stringData\":{\"AUTH_SECRET\":\"${NEW_SECRET}\"}}"

oc rollout restart deployment/myss-frontend -n ${NAMESPACE}
oc rollout status deployment/myss-frontend -n ${NAMESPACE} --timeout=5m
```

---

## Verification After Any Rotation

```bash
# Confirm pods are running (not CrashLoopBackOff)
oc get pods -n ${NAMESPACE} -l app=myss

# API health
oc port-forward deployment/myss-api 8000:8000 -n ${NAMESPACE} &
curl -s http://localhost:8000/health

# Frontend health
oc port-forward deployment/myss-frontend 3000:3000 -n ${NAMESPACE} &
curl -s http://localhost:3000/health

# End-to-end: sign in with a test account and verify the dashboard loads
```

If any pod enters `CrashLoopBackOff`, check logs with `oc logs --previous deployment/<name>` and verify the secret values are correct.
