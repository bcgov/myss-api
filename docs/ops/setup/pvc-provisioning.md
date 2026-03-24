# PVC Provisioning

**Audience:** Platform/ops engineer.
**Read time:** ~15 minutes.
**When to use:** New environment provisioning. PVCs must exist before the PostgreSQL
and Redis pods can start.

---

## Prerequisites

- OpenShift project `myss-<env>` exists (see [openshift-project-setup.md](./openshift-project-setup.md))
- You have `oc` access to the target namespace
- A storage class is available that supports `ReadWriteOnce`

---

## 1. Check Available Storage Classes

```bash
oc get sc
```

Identify a storage class appropriate for database workloads. On BC Gov OpenShift clusters,
common storage classes include `netapp-block-standard` (block storage, good for databases)
and `netapp-file-standard` (file storage). Block storage is preferred for PostgreSQL.

Note the storage class name — you will need it in the PVC manifests below if the cluster
does not have a default storage class.

---

## 2. PostgreSQL PVC

**Claimed by:** `openshift/postgres-deployment.yaml` — the postgres deployment references
`claimName: myss-postgres-pvc`.

The PVC spec is embedded in `openshift/postgres-deployment.yaml`. It will be created
automatically when you apply that manifest. If you need to pre-create it separately
(e.g. to verify binding before deploying the workload):

```yaml
# postgres-pvc-standalone.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: myss-postgres-pvc
  namespace: myss-${ENV}
  labels:
    app: myss
    component: postgres
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  # storageClassName: netapp-block-standard  # uncomment and set if no default storage class
```

Apply:

```bash
oc apply -f postgres-pvc-standalone.yaml -n myss-${ENV}
```

The PVC will remain in `Pending` status until a pod mounts it (dynamic provisioning
does not bind until first use on most clusters). This is normal.

---

## 3. Redis PVC

**Claimed by:** `openshift/redis-deployment.yaml` — the redis deployment references
`claimName: myss-redis-pvc`.

Redis uses append-only file (AOF) persistence (`--appendonly yes`). The PVC must be
available before the Redis pod starts.

```yaml
# redis-pvc-standalone.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: myss-redis-pvc
  namespace: myss-${ENV}
  labels:
    app: myss
    component: redis
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
  # storageClassName: netapp-block-standard  # uncomment and set if no default storage class
```

Apply:

```bash
oc apply -f redis-pvc-standalone.yaml -n myss-${ENV}
```

---

## 4. Verify PVCs

After applying the workload manifests (or the standalone PVC files above):

```bash
oc get pvc -n myss-${ENV}
```

Expected output once pods are running:

```
NAME                STATUS   VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS            AGE
myss-postgres-pvc   Bound    pv-xxx   10Gi       RWO            netapp-block-standard   5m
myss-redis-pvc      Bound    pv-yyy   2Gi        RWO            netapp-block-standard   5m
```

If a PVC stays in `Pending` after the pod has been scheduled, check events:

```bash
oc describe pvc myss-postgres-pvc -n myss-${ENV}
```

Common causes: storage class does not exist, quota exceeded, or no available capacity.

---

## 5. Storage Monitoring

### Check current disk usage (PostgreSQL)

```bash
oc exec deployment/myss-postgres -n myss-${ENV} -- df -h /var/lib/postgresql/data
```

### Check current disk usage (Redis)

```bash
oc exec deployment/myss-redis -n myss-${ENV} -- df -h /data
```

Alert at 80% usage — with 10 Gi provisioned for PostgreSQL, that is 8 Gi used.
With 2 Gi for Redis, that is 1.6 Gi used.

Set up a monitoring alert or schedule a weekly check in the first months after launch.

---

## 6. Expanding a PVC

If a PVC is running low, expand it (requires the storage class to support `allowVolumeExpansion: true`):

```bash
# Example: expand postgres PVC to 20Gi
oc patch pvc myss-postgres-pvc -n myss-${ENV} \
  -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'

# Verify the resize request
oc describe pvc myss-postgres-pvc -n myss-${ENV}
```

The postgres pod may need to be restarted for the filesystem to pick up the new size,
depending on the storage driver.

---

## 7. Backup

PVCs are not automatically backed up. See the backup runbook for the procedure to
schedule PostgreSQL dumps.

Link: `docs/ops/runbooks/pvc-backup-restore.md`

---

## Summary of PVC Specifications

| PVC name | Mount path | Size | Access mode | Used by |
|---|---|---|---|---|
| `myss-postgres-pvc` | `/var/lib/postgresql/data` | 10 Gi | ReadWriteOnce | `myss-postgres` |
| `myss-redis-pvc` | `/data` | 2 Gi | ReadWriteOnce | `myss-redis` |

---

## Next Steps

- **[Database initialization](./database-initialization.md)** — deploy PostgreSQL and run the initial Alembic migrations
