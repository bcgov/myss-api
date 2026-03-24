# Runbook: Troubleshooting

## Context

This runbook covers diagnosis and resolution of the most common operational issues in the MySS 2.0 environment. All commands assume you are authenticated to the relevant OpenShift namespace:

```bash
export NAMESPACE=myss-prod   # or myss-test1, myss-test2, etc.
```

---

## 1. Pod Crash Loops

### Symptoms

`oc get pods` shows a pod with `CrashLoopBackOff` or repeated `Error` restarts.

### Diagnosis

```bash
# Check pod status and restart count
oc get pods -n ${NAMESPACE} -l app=myss

# Describe the pod for events (often reveals the root cause immediately)
oc describe pod <pod-name> -n ${NAMESPACE}

# Logs from the currently running (crashing) container
oc logs <pod-name> -n ${NAMESPACE}

# Logs from the previous (crashed) container — most useful for crash diagnosis
oc logs --previous <pod-name> -n ${NAMESPACE}

# Or via deployment reference
oc logs --previous deployment/myss-api -n ${NAMESPACE}
```

### Common causes and fixes

**Missing secret or wrong secret key**

Symptom in `oc describe pod`: `CreateContainerConfigError` or `Error: secret "myss-db-secret" not found`.

Fix: Verify all required secrets exist and have the correct keys (see [secrets-rotation.md](./secrets-rotation.md) for the full inventory).

```bash
oc get secret myss-db-secret myss-redis-secret myss-icm-secret myss-auth-secret myss-mail-secret \
  -n ${NAMESPACE}
```

**Database unreachable**

Symptom in logs: `sqlalchemy.exc.OperationalError: could not connect to server` or `connection refused`.

```bash
# Is the postgres pod running?
oc get pods -n ${NAMESPACE} -l app=myss,component=postgres

# Can the API pod reach postgres?
oc exec deployment/myss-api -n ${NAMESPACE} -- \
  python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}'); print('OK')"
```

**Alembic migration failure (init container)**

The `alembic-migrate` init container must complete successfully before the main container starts. If it fails, the pod stays in `Init:Error` or `Init:CrashLoopBackOff`.

```bash
# Get init container logs
oc logs <pod-name> -c alembic-migrate -n ${NAMESPACE}
```

See section 5 (Migration Failures) for full diagnosis.

**Out of Memory (OOM)**

Symptom: `OOMKilled` in `oc describe pod` under `Last State`. The API container limit is 512Mi; the frontend limit is 256Mi.

```bash
oc describe pod <pod-name> -n ${NAMESPACE} | grep -A5 "Last State"
# Look for: Reason: OOMKilled
```

Fix: Temporarily increase the memory limit, or investigate the memory leak before scaling.

```bash
oc set resources deployment/myss-api \
  --limits=memory=1Gi -n ${NAMESPACE}
```

---

## 2. Siebel (ICM) Circuit Breaker Open

### Symptoms

- API responses return HTTP 503 with body containing: `ICM circuit breaker is open; service unavailable`
- Or: `ICM circuit breaker: probe already in flight`
- Users see an error page when accessing case data, payments, or service requests

### How the circuit breaker works

From `myss-api/app/services/icm/client.py`:

- Threshold: 5 consecutive failures → circuit opens
- Recovery: after 30 seconds (`reset_timeout=30.0`), the circuit enters HALF_OPEN and allows one probe request
- If the probe succeeds, the circuit closes; if it fails, it re-opens for another 30 seconds
- Retries: 3 attempts with exponential backoff (1s, 2s, 4s) on 5xx and connection errors; 4xx errors are not retried

### Diagnosis

```bash
# Check for circuit breaker log events
oc logs deployment/myss-api -n ${NAMESPACE} | grep -i "circuit_breaker"
# Look for: circuit_breaker_opened, event=circuit_breaker_opened, failures=5

# Check ICM connectivity directly
oc exec deployment/myss-api -n ${NAMESPACE} -- \
  curl -s -o /dev/null -w "%{http_code}" \
  -X POST ${ICM_TOKEN_URL} \
  -d "grant_type=client_credentials&client_id=${ICM_CLIENT_ID}&client_secret=${ICM_CLIENT_SECRET}"
# Expected: 200. Anything else indicates ICM OAuth2 is down or credentials are wrong.
```

### Auto-recovery

The circuit breaker recovers automatically after 30 seconds if ICM becomes healthy again. No manual intervention is required unless ICM remains down or credentials are wrong.

### Manual reset (if ICM is healthy but circuit is stuck)

Restart the API deployment — the circuit breaker state is in-memory and resets on pod restart:

```bash
oc rollout restart deployment/myss-api -n ${NAMESPACE}
oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
```

### Checking ICM credentials

```bash
# Retrieve current ICM credentials from the secret
ICM_CLIENT_ID=$(oc get secret myss-icm-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.ICM_CLIENT_ID}' | base64 --decode)
ICM_TOKEN_URL=$(oc get secret myss-icm-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.ICM_TOKEN_URL}' | base64 --decode)
# ICM_CLIENT_SECRET — retrieve but do not print; use only in curl call
```

If credentials are wrong, follow [secrets-rotation.md](./secrets-rotation.md) to update `myss-icm-secret` and restart the API.

---

## 3. Database Connection Exhaustion

### Symptoms

- API logs: `too many connections` or `remaining connection slots are reserved for non-replication superuser connections`
- HTTP 500 errors on endpoints that query the database

### Diagnosis

```bash
# Check active connections
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=${POSTGRES_DB} -c \
  "SELECT count(*), state, wait_event_type, wait_event
   FROM pg_stat_activity
   WHERE datname = '${POSTGRES_DB}'
   GROUP BY state, wait_event_type, wait_event
   ORDER BY count DESC;"

# Check max_connections setting
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=postgres -c \
  "SHOW max_connections;"

# Identify long-running or idle-in-transaction connections
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=${POSTGRES_DB} -c \
  "SELECT pid, usename, application_name, state, query_start, state_change, query
   FROM pg_stat_activity
   WHERE datname = '${POSTGRES_DB}'
     AND state != 'idle'
   ORDER BY query_start;"
```

### Pool settings

The API uses SQLAlchemy's connection pool. Current pool settings are configured in the application code. Check `myss-api/app/database.py` (or equivalent) for `pool_size` and `max_overflow` values.

### Resolution

Terminate idle/stuck connections if necessary:

```bash
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=postgres -c \
  "SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE datname = '${POSTGRES_DB}'
     AND state = 'idle in transaction'
     AND state_change < now() - interval '5 minutes';"
```

If the pool is exhausted due to load, consider restarting the API (which resets all connections) or temporarily reducing `max_overflow`.

---

## 4. Redis Connectivity

### Symptoms

- API logs: `redis.exceptions.ConnectionError` or `redis.exceptions.AuthenticationError`
- Sessions appear to not persist; users are logged out immediately
- Cache keys are not being set

### Diagnosis

```bash
# Retrieve password for redis-cli
REDIS_PASSWORD=$(oc get secret myss-redis-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.REDIS_PASSWORD}' | base64 --decode)

# Ping Redis from inside the Redis pod
oc exec deployment/myss-redis -n ${NAMESPACE} -- \
  redis-cli -a ${REDIS_PASSWORD} PING
# Expected: PONG

# Ping Redis from inside the API pod (tests network path)
oc exec deployment/myss-api -n ${NAMESPACE} -- \
  redis-cli -h myss-redis -p 6379 -a ${REDIS_PASSWORD} PING
# Expected: PONG

# Check Redis pod status
oc get pods -n ${NAMESPACE} -l app=myss,component=redis
```

### Password mismatch

If the API can reach Redis but gets `NOAUTH` or `WRONGPASS`, the `REDIS_PASSWORD` in `myss-redis-secret` may not match the password Redis was started with.

```bash
# Check what password Redis is using (from environment)
oc exec deployment/myss-redis -n ${NAMESPACE} -- \
  sh -c 'echo $REDIS_PASSWORD'
# Compare to the value in the secret

# Check what password the API is using
oc exec deployment/myss-api -n ${NAMESPACE} -- \
  sh -c 'echo $REDIS_PASSWORD'
```

If mismatched, update the secret to a single consistent value and restart both deployments. See [secrets-rotation.md](./secrets-rotation.md).

### Session TTL reference

From `myss-api/app/cache/keys.py`:

| Key pattern | TTL | Purpose |
|---|---|---|
| `session:<user_id>` | 900s (15 min) | Auth.js session data |
| `icm_cache:case:<case_number>` | 300s (5 min) | ICM case status cache |
| `icm_cache:payment:<case_number>` | 3600s (1 hr) | ICM payment cache |
| `icm_cache:cheque_schedule:<case_number>` | 3600s (1 hr) | Cheque schedule cache |
| `icm_cache:banners:<case_number>` | 300s (5 min) | Banner notification cache |
| `support_view:<worker_idir>` | 900s (15 min) | Worker support-view session |
| `pin_reset:<profile_id>` | 3600s (1 hr) | PIN reset rate-limit |

---

## 5. Migration Failures

### Symptoms

- New API pods stuck in `Init:Error` or `Init:CrashLoopBackOff`
- `oc get pods` shows `0/1` ready with repeated restarts for the init container

### Diagnosis

```bash
# Get the pod name
POD=$(oc get pods -n ${NAMESPACE} -l app=myss,component=api \
  --sort-by=.metadata.creationTimestamp -o name | tail -1)

# Read the init container logs
oc logs ${POD} -c alembic-migrate -n ${NAMESPACE}
```

Common errors in Alembic output:

| Error message | Cause | Fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: could not connect to server` | PostgreSQL unreachable | Fix DB connectivity first; see section 3 |
| `Target database is not up to date` | Alembic version mismatch | Check `alembic_version` table; manually run `alembic upgrade head` if safe |
| `Can't locate revision identified by ...` | Migration file missing from image | Ensure correct image was deployed |
| `DuplicateTable` / `column already exists` | Migration not idempotent | Migration was partially applied; may need manual cleanup |

### Force-running Alembic in a debug pod

```bash
oc run alembic-debug \
  --image=ghcr.io/${GITHUB_ORG}/myss-api:${IMAGE_TAG} \
  --restart=Never \
  --env-from=secret/myss-db-secret \
  --env-from=configmap/myss-api-config \
  -n ${NAMESPACE} \
  -- alembic upgrade head

oc logs -f alembic-debug -n ${NAMESPACE}
oc delete pod alembic-debug -n ${NAMESPACE}
```

For rollback of a failed migration, see [rollback.md](./rollback.md).

---

## 6. GitHub Actions Failures

### Common causes

| Failure point | Cause | Fix |
|---|---|---|
| `Log in to Container Registry` step fails | `GITHUB_TOKEN` lacks `packages: write` permission | Check repository permissions; confirm `permissions.packages: write` in workflow |
| `Build and push API image` fails | Docker build error | Review build output; check `myss-api/Dockerfile` |
| `Log in to OpenShift` fails | `OPENSHIFT_TOKEN` expired or wrong | Rotate the service account token and update the GitHub secret |
| `oc set image` fails | Deployment not found or namespace wrong | Verify `OPENSHIFT_NAMESPACE` secret value matches actual namespace |
| `oc rollout status --timeout=5m` exits non-zero | Pods failing readiness probes | See section 1 (Pod Crash Loops) |

### Retrieve GitHub Actions logs

Use the GitHub CLI:

```bash
# List recent workflow runs
gh run list --workflow=deploy.yml --limit=10

# View a specific run
gh run view <run-id>

# Watch a run in progress
gh run watch <run-id>

# Download logs
gh run view <run-id> --log
```

---

## 7. Session Issues

### Symptoms

- Users are immediately redirected to login after signing in
- Session data appears missing between page loads
- `401 Unauthorized` responses from the API despite the user appearing logged in

### Diagnosis

**Redis not reachable** (most common): see section 4.

**JWT validation failure**

The frontend uses `AUTH_SECRET` (from `myss-auth-secret`) to sign session JWTs. If the key was rotated and the frontend was not restarted, it may be validating tokens with a stale key in memory. Restart the frontend:

```bash
oc rollout restart deployment/myss-frontend -n ${NAMESPACE}
```

If `AUTH_SECRET` itself was rotated, all existing sessions are immediately invalid. Users must re-authenticate. See [secrets-rotation.md](./secrets-rotation.md) for the JWT rotation procedure.

**Session TTL**

Sessions expire after 900 seconds (15 minutes) of inactivity (`SESSION_TTL = 900` in `myss-api/app/cache/keys.py`). The frontend warns users at 14 minutes (`SESSION_WARNING_MINUTES: "14"` in `myss-frontend-config`). This is expected behaviour, not a bug.

**Inspect a session key in Redis**

```bash
REDIS_PASSWORD=$(oc get secret myss-redis-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.REDIS_PASSWORD}' | base64 --decode)

# Check if a session key exists (substitute actual user UUID)
oc exec deployment/myss-redis -n ${NAMESPACE} -- \
  redis-cli -a ${REDIS_PASSWORD} TTL "session:<user-uuid>"
# -2 means key does not exist; positive number is seconds remaining
```
