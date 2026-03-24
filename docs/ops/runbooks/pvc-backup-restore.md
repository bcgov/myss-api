# Runbook: PVC Backup and Restore

## Context

Two stateful workloads use PersistentVolumeClaims in OpenShift:

| Workload | PVC | Size | Data criticality |
|---|---|---|---|
| `myss-postgres` (postgres:16) | `myss-postgres-pvc` | 10Gi | Critical — primary application database |
| `myss-redis` (redis:7) | `myss-redis-pvc` | 2Gi | Tolerable loss — sessions and cache only |

PostgreSQL data is the primary backup concern. Redis data loss is acceptable: active sessions will be invalidated (users must re-authenticate), and all ICM cache entries will be re-populated on demand.

---

## PostgreSQL Backup

### Ad-hoc backup via `oc exec`

Run a `pg_dump` directly from inside the postgres pod. The dump is written to stdout and piped to a local file.

```bash
NAMESPACE=myss-prod
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="myss-postgres-${TIMESTAMP}.dump"

oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  pg_dump \
    --username=${POSTGRES_USER} \
    --dbname=${POSTGRES_DB} \
    --format=custom \
    --no-password \
  > ${BACKUP_FILE}

echo "Backup written to: ${BACKUP_FILE}"
ls -lh ${BACKUP_FILE}
```

The `--format=custom` flag produces a compressed binary dump compatible with `pg_restore`. The credential values (`POSTGRES_USER`, `POSTGRES_DB`) come from `myss-db-secret`; set them in your shell or substitute directly.

```bash
# Retrieve values from the secret (requires oc access)
POSTGRES_USER=$(oc get secret myss-db-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.POSTGRES_USER}' | base64 --decode)
POSTGRES_DB=$(oc get secret myss-db-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.POSTGRES_DB}' | base64 --decode)
```

### Scheduled CronJob backup

A CronJob should be deployed to automate daily backups. The job should:

1. Run `pg_dump` inside a sidecar container with access to the postgres Service (`myss-postgres:5432`)
2. Write the dump to an off-cluster object store (e.g., BC Government S3-compatible storage) or a separate PVC used solely for backups
3. Retain at least 7 daily and 4 weekly backups, pruning older files automatically

Example CronJob skeleton (adapt for your object store):

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: myss-postgres-backup
spec:
  schedule: "0 2 * * *"   # 02:00 UTC daily
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: pg-backup
              image: postgres:16
              envFrom:
                - secretRef:
                    name: myss-db-secret
              command:
                - /bin/sh
                - -c
                - |
                  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
                  pg_dump \
                    --host=myss-postgres \
                    --port=5432 \
                    --username=${POSTGRES_USER} \
                    --dbname=${POSTGRES_DB} \
                    --format=custom \
                    > /backup/myss-${TIMESTAMP}.dump
                  echo "Backup complete: myss-${TIMESTAMP}.dump"
              volumeMounts:
                - name: backup-storage
                  mountPath: /backup
          volumes:
            - name: backup-storage
              persistentVolumeClaim:
                claimName: myss-backup-pvc   # separate 50Gi PVC for backups
```

### Testing restores

Restore procedures must be tested regularly (at least monthly). An untested backup is not a backup.

---

## PostgreSQL Restore

### Step 1 — Confirm backup file integrity

```bash
pg_restore --list ${BACKUP_FILE} | head -20
# Should print a table-of-contents without errors
```

### Step 2 — Scale down the API to prevent writes during restore

```bash
oc scale deployment/myss-api --replicas=0 -n ${NAMESPACE}
oc scale deployment/myss-celery --replicas=0 -n ${NAMESPACE}
```

### Step 3 — Drop and recreate the target database

```bash
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}';"

oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=postgres -c \
  "DROP DATABASE IF EXISTS ${POSTGRES_DB};"

oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=postgres -c \
  "CREATE DATABASE ${POSTGRES_DB};"
```

### Step 4 — Copy the backup file into the pod and restore

```bash
# Copy dump file into the pod
oc cp ${BACKUP_FILE} \
  $(oc get pod -n ${NAMESPACE} -l app=myss,component=postgres -o name | head -1 | cut -d/ -f2):/tmp/${BACKUP_FILE} \
  -n ${NAMESPACE}

# Run pg_restore
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  pg_restore \
    --username=${POSTGRES_USER} \
    --dbname=${POSTGRES_DB} \
    --no-password \
    --verbose \
    /tmp/${BACKUP_FILE}
```

### Step 5 — Scale the API back up

```bash
oc scale deployment/myss-api --replicas=2 -n ${NAMESPACE}
oc scale deployment/myss-celery --replicas=1 -n ${NAMESPACE}
oc rollout status deployment/myss-api -n ${NAMESPACE} --timeout=5m
```

The Alembic init container will run `alembic upgrade head` on startup. If restoring to a point earlier than the current schema, you may need to pin the API image to a version compatible with the restored schema version.

### Step 6 — Verify

```bash
oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=${POSTGRES_DB} -c \
  "\dt"
# Should list all application tables

oc exec deployment/myss-postgres -n ${NAMESPACE} -- \
  psql --username=${POSTGRES_USER} --dbname=${POSTGRES_DB} -c \
  "SELECT version_num FROM alembic_version;"
```

---

## Redis Backup

Redis stores only ephemeral data:
- Sessions (`session:<user_id>`, TTL 900s)
- ICM case/payment/banner cache (TTL 300–3600s)
- Worker support-view sessions (TTL 900s)
- PIN reset rate-limit keys (TTL 3600s)

Loss of Redis data forces users to re-authenticate and clears all ICM caches. ICM caches self-populate on the next API call. This is operationally disruptive but causes no data loss.

### Backup for disaster recovery (optional)

Redis is configured with `--appendonly yes`, so the AOF log on `myss-redis-pvc` (2Gi) provides crash recovery within a single pod restart. For a full off-cluster backup:

```bash
# Trigger a background save
oc exec deployment/myss-redis -n ${NAMESPACE} -- \
  redis-cli -a ${REDIS_PASSWORD} BGSAVE

# Wait for save to complete (LASTSAVE returns a Unix timestamp)
oc exec deployment/myss-redis -n ${NAMESPACE} -- \
  redis-cli -a ${REDIS_PASSWORD} LASTSAVE

# Copy the dump file off the pod
oc cp \
  $(oc get pod -n ${NAMESPACE} -l app=myss,component=redis -o name | head -1 | cut -d/ -f2):/data/dump.rdb \
  ./redis-dump-$(date +%Y%m%d).rdb \
  -n ${NAMESPACE}
```

Retrieve `REDIS_PASSWORD` from the secret:

```bash
REDIS_PASSWORD=$(oc get secret myss-redis-secret -n ${NAMESPACE} \
  -o jsonpath='{.data.REDIS_PASSWORD}' | base64 --decode)
```

### Redis restore

Given that Redis data is ephemeral and non-critical, restore is only warranted in a full environment rebuild. Copy a `dump.rdb` into `/data/` on the Redis pod and restart the deployment. Users will be required to re-authenticate.

```bash
oc cp redis-dump-YYYYMMDD.rdb \
  $(oc get pod -n ${NAMESPACE} -l app=myss,component=redis -o name | head -1 | cut -d/ -f2):/data/dump.rdb \
  -n ${NAMESPACE}

oc rollout restart deployment/myss-redis -n ${NAMESPACE}
```
