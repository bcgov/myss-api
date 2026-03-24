# Vault Integration Setup

**Audience:** Platform/ops engineer with Vault admin access.
**Read time:** ~20 minutes.
**When to use:** New environment provisioning. Run after the OpenShift project is created.

---

## Prerequisites

- OpenShift project `myss-<env>` exists (see [openshift-project-setup.md](./openshift-project-setup.md))
- Vault CLI (`vault`) installed and authenticated as an admin
- Kubernetes authentication method already enabled on the Vault instance
- The Vault instance is reachable from the OpenShift cluster

---

## Overview

MySS stores all secrets in HashiCorp Vault under the path `secret/data/myss/<env>/`.
Secrets are injected into OpenShift as native Kubernetes `Secret` objects.

**The exact injection mechanism depends on what is available in your cluster.**
Three common patterns are supported:

| Pattern | When to use |
|---|---|
| **Vault Agent sidecar** | Vault Agent Injector is installed on the cluster |
| **External Secrets Operator** | ESO is installed on the cluster |
| **Manual sync** | Neither is available; use `vault kv get` + `oc create secret` |

This guide covers all three. Confirm with your cluster operator which pattern is in use.

---

## 1. Secret Paths and Keys

All MySS secrets live under `secret/data/myss/<env>/`. The sub-paths correspond
to the Kubernetes secret names used in the manifests.

### `secret/data/myss/<env>/db`

Maps to Kubernetes secret `myss-db-secret`.

| Key | Description |
|---|---|
| `DATABASE_URL` | Full async DSN, e.g. `postgresql+asyncpg://user:pass@myss-postgres:5432/myss` |
| `POSTGRES_USER` | PostgreSQL superuser (must match DATABASE_URL) |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name, e.g. `myss` |

### `secret/data/myss/<env>/redis`

Maps to Kubernetes secret `myss-redis-secret`.

| Key | Description |
|---|---|
| `REDIS_URL` | Full Redis URL, e.g. `redis://:password@myss-redis:6379/0` |
| `REDIS_PASSWORD` | Redis `requirepass` value (same password as in REDIS_URL) |

### `secret/data/myss/<env>/icm`

Maps to Kubernetes secret `myss-icm-secret`.

| Key | Description |
|---|---|
| `ICM_CLIENT_ID` | OAuth2 client ID for Siebel REST API |
| `ICM_CLIENT_SECRET` | OAuth2 client secret |
| `ICM_TOKEN_URL` | Token endpoint, e.g. `https://loginproxy.gov.bc.ca/auth/...` |

### `secret/data/myss/<env>/auth`

Maps to Kubernetes secret `myss-auth-secret`.

| Key | Description |
|---|---|
| `AUTH_SECRET` | Auth.js signing key — minimum 32 random bytes, base64-encoded |
| `AUTH_TRUST_HOST` | Set to `true` (literal string) for all deployed environments |

### `secret/data/myss/<env>/mail`

Maps to Kubernetes secret `myss-mail-secret`.

| Key | Description |
|---|---|
| `MAILJET_API_KEY` | MailJet HTTP API v3.1 key |
| `MAILJET_API_SECRET` | MailJet API secret |

---

## 2. Initial Secret Seeding

Write each secret to Vault. Replace placeholder values with real credentials.

```bash
ENV=dev1   # set for your environment

# Database
vault kv put secret/myss/${ENV}/db \
  DATABASE_URL="postgresql+asyncpg://myss:CHANGEME@myss-postgres:5432/myss" \
  POSTGRES_USER="myss" \
  POSTGRES_PASSWORD="CHANGEME" \
  POSTGRES_DB="myss"

# Redis
vault kv put secret/myss/${ENV}/redis \
  REDIS_URL="redis://:CHANGEME@myss-redis:6379/0" \
  REDIS_PASSWORD="CHANGEME"

# ICM / Siebel
vault kv put secret/myss/${ENV}/icm \
  ICM_CLIENT_ID="CHANGEME" \
  ICM_CLIENT_SECRET="CHANGEME" \
  ICM_TOKEN_URL="https://loginproxy.gov.bc.ca/auth/realms/standard/protocol/openid-connect/token"

# Auth.js
AUTH_SECRET=$(openssl rand -base64 32)
vault kv put secret/myss/${ENV}/auth \
  AUTH_SECRET="${AUTH_SECRET}" \
  AUTH_TRUST_HOST="true"

# MailJet
vault kv put secret/myss/${ENV}/mail \
  MAILJET_API_KEY="CHANGEME" \
  MAILJET_API_SECRET="CHANGEME"
```

Verify:

```bash
vault kv list secret/myss/${ENV}/
# Expected: db  redis  icm  auth  mail
```

---

## 3. Vault Policy

Create a policy that allows the application to read (but not write) its own secrets.

```hcl
# myss-<env>-policy.hcl
path "secret/data/myss/<env>/*" {
  capabilities = ["read", "list"]
}

path "secret/metadata/myss/<env>/*" {
  capabilities = ["list"]
}
```

Apply:

```bash
vault policy write myss-${ENV} myss-${ENV}-policy.hcl
```

---

## 4. Kubernetes Authentication Method

This step binds an OpenShift service account to the Vault policy so that pods can
authenticate to Vault without static credentials.

```bash
# Enable Kubernetes auth if not already enabled
vault auth enable kubernetes   # skip if already enabled

# Configure with the OpenShift cluster's API endpoint
vault write auth/kubernetes/config \
  kubernetes_host="https://api.<cluster-domain>:6443" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# Create the role binding
vault write auth/kubernetes/role/myss-${ENV} \
  bound_service_account_names=default \
  bound_service_account_namespaces=myss-${ENV} \
  policies=myss-${ENV} \
  ttl=1h
```

The `kubernetes_host` and CA cert path vary by cluster. Confirm with your platform team.

---

## 5. Secret Injection

### Option A: Vault Agent Sidecar

If the Vault Agent Injector is installed, annotate the API and Celery deployments.
The injector will write secrets as files or environment variables into the pod.

This option requires patching the deployment manifests with Vault annotations.
Consult the [Vault Agent Injector documentation](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)
for the specific annotations. This pattern is not yet implemented in the current
manifests — coordinate with your platform team before adopting it.

### Option B: External Secrets Operator

If ESO is installed, create `ExternalSecret` resources that pull from Vault and
create native Kubernetes `Secret` objects matching the names in the manifests.

```yaml
# external-secret-db.yaml (example)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myss-db-secret
  namespace: myss-${ENV}
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: myss-db-secret
  dataFrom:
    - extract:
        key: secret/myss/${ENV}/db
```

Repeat for `redis`, `icm`, `auth`, and `mail`. The `ClusterSecretStore` name
(`vault-backend`) must match what is configured in your cluster.

### Option C: Manual Sync

If neither injector nor ESO is available, create Kubernetes secrets directly
from Vault values. This must be re-run whenever secrets rotate.

```bash
ENV=dev1

# Database
vault kv get -format=json secret/myss/${ENV}/db | \
  jq -r '.data.data | to_entries[] | "--from-literal=\(.key)=\(.value)"' | \
  xargs oc create secret generic myss-db-secret -n myss-${ENV}

# Redis
vault kv get -format=json secret/myss/${ENV}/redis | \
  jq -r '.data.data | to_entries[] | "--from-literal=\(.key)=\(.value)"' | \
  xargs oc create secret generic myss-redis-secret -n myss-${ENV}

# ICM
vault kv get -format=json secret/myss/${ENV}/icm | \
  jq -r '.data.data | to_entries[] | "--from-literal=\(.key)=\(.value)"' | \
  xargs oc create secret generic myss-icm-secret -n myss-${ENV}

# Auth
vault kv get -format=json secret/myss/${ENV}/auth | \
  jq -r '.data.data | to_entries[] | "--from-literal=\(.key)=\(.value)"' | \
  xargs oc create secret generic myss-auth-secret -n myss-${ENV}

# Mail
vault kv get -format=json secret/myss/${ENV}/mail | \
  jq -r '.data.data | to_entries[] | "--from-literal=\(.key)=\(.value)"' | \
  xargs oc create secret generic myss-mail-secret -n myss-${ENV}
```

---

## 6. Verification

```bash
oc get secrets -n myss-${ENV} | grep myss
```

Expected secrets:

```
myss-db-secret      Opaque   4   <age>
myss-redis-secret   Opaque   2   <age>
myss-icm-secret     Opaque   3   <age>
myss-auth-secret    Opaque   2   <age>
myss-mail-secret    Opaque   2   <age>
```

Verify key names without revealing values:

```bash
oc get secret myss-db-secret -n myss-${ENV} \
  -o jsonpath='{.data}' | jq 'keys'
# Expected: ["DATABASE_URL","POSTGRES_DB","POSTGRES_PASSWORD","POSTGRES_USER"]
```

---

## 7. Secret Rotation

When rotating a secret:

1. Update the value in Vault: `vault kv patch secret/myss/${ENV}/db POSTGRES_PASSWORD=NEW_VALUE`
2. Re-sync to Kubernetes (ESO refreshes automatically on its `refreshInterval`; manual sync requires re-running the `oc create secret` commands with `--dry-run=client -o yaml | oc apply -f -`)
3. Restart the affected deployments to pick up the new secret values:
   ```bash
   oc rollout restart deployment/myss-api -n myss-${ENV}
   oc rollout restart deployment/myss-celery -n myss-${ENV}
   ```

---

## Next Steps

- **[PVC provisioning](./pvc-provisioning.md)** — persistent volumes must exist before workloads start
- **[Database initialization](./database-initialization.md)** — run migrations after secrets are in place
