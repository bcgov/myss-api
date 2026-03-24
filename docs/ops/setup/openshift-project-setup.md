# OpenShift Project Setup

**Audience:** Platform/ops engineer standing up a new MySS environment from scratch.
**Read time:** ~30 minutes.
**When to use:** New environment provisioning or full disaster recovery.

---

## Prerequisites

- `oc` CLI installed and able to reach the cluster
- Cluster-admin or project-creator rights
- ghcr.io pull credentials for the GitHub org that hosts `myss-api` and `myss-frontend` images

---

## 1. Create the Project

Environments map one-to-one with OpenShift projects. Valid environment suffixes are:
`dev1`, `dev2`, `test1`, `test2`, `test3`, `practice`, `preprod`, `prod`.

```bash
ENV=dev1   # replace for each environment

oc new-project myss-${ENV} \
  --display-name="MySelfServe — ${ENV^^}" \
  --description="MySS 2.0 income-assistance self-service portal (${ENV})"
```

Verify:

```bash
oc project myss-${ENV}
```

---

## 2. Apply Standard Labels

All manifests in `openshift/` use `app=myss` plus a `component` label. Apply the same
label to the project itself for cost-attribution and tooling:

```bash
oc label namespace myss-${ENV} \
  app.kubernetes.io/part-of=myss \
  environment=${ENV} \
  ministry=SDPR
```

### Component labels used across manifests

| Component   | `app` label | `component` label |
|-------------|-------------|-------------------|
| API         | `myss`      | `api`             |
| Frontend    | `myss`      | `frontend`        |
| PostgreSQL  | `myss`      | `postgres`        |
| Redis       | `myss`      | `redis`           |
| Celery      | `myss`      | `celery`          |
| Migration   | `myss`      | `migration`       |

These labels are used by Services as selectors, so they must match exactly.

---

## 3. Resource Quotas

Apply a quota appropriate to the environment. Adjust values for production.

```yaml
# resource-quota.yaml  (not committed — apply manually per environment)
apiVersion: v1
kind: ResourceQuota
metadata:
  name: myss-quota
  namespace: myss-${ENV}
spec:
  hard:
    pods: "20"
    requests.cpu: "2"
    requests.memory: "2Gi"
    limits.cpu: "6"
    limits.memory: "6Gi"
    persistentvolumeclaims: "5"
    requests.storage: "50Gi"
```

Apply:

```bash
oc apply -f resource-quota.yaml -n myss-${ENV}
oc describe quota myss-quota -n myss-${ENV}
```

Production quotas should be reviewed with the platform team before applying.

---

## 4. Image Pull Secret for ghcr.io

The API and frontend images are pushed to GitHub Container Registry (`ghcr.io`).
OpenShift needs a pull secret to fetch them.

Create a personal access token (PAT) in GitHub with `read:packages` scope, then:

```bash
GITHUB_USER=<your-github-username>
GITHUB_PAT=<your-pat>

oc create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=${GITHUB_USER} \
  --docker-password=${GITHUB_PAT} \
  --docker-email=${GITHUB_USER}@users.noreply.github.com \
  -n myss-${ENV}
```

Link the secret to the default service account so all pods can pull automatically:

```bash
oc secrets link default ghcr-pull-secret --for=pull -n myss-${ENV}
```

Verify:

```bash
oc get secret ghcr-pull-secret -n myss-${ENV}
```

---

## 5. Network Policies

The default OpenShift network policy denies all ingress between namespaces. Apply
the following policies to allow required internal traffic while restricting external access
to the public Route only.

### 5a. Allow internal service communication

```yaml
# netpol-allow-internal.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-internal
  namespace: myss-${ENV}
  labels:
    app: myss
spec:
  podSelector:
    matchLabels:
      app: myss
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: myss
  policyTypes:
    - Ingress
```

This allows all `app=myss` pods to reach each other — API to PostgreSQL (5432),
API to Redis (6379), Celery to Redis (6379), and Celery to PostgreSQL (5432).

### 5b. Allow OpenShift router to reach the frontend

```yaml
# netpol-allow-router.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-router-to-frontend
  namespace: myss-${ENV}
  labels:
    app: myss
spec:
  podSelector:
    matchLabels:
      app: myss
      component: frontend
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              network.openshift.io/policy-group: ingress
  policyTypes:
    - Ingress
```

### 5c. Deny all other ingress by default

```yaml
# netpol-deny-default.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: myss-${ENV}
  labels:
    app: myss
spec:
  podSelector: {}
  policyTypes:
    - Ingress
```

Apply all three:

```bash
oc apply -f netpol-deny-default.yaml -n myss-${ENV}
oc apply -f netpol-allow-internal.yaml -n myss-${ENV}
oc apply -f netpol-allow-router.yaml -n myss-${ENV}
```

Note: The API service is `ClusterIP` only and has no Route, so it is not directly
reachable from outside the cluster. Only `myss-frontend` has a Route exposed.

---

## 6. Service Accounts and Role Bindings

### Deploy service account (for CI/CD)

The GitHub Actions deploy pipeline authenticates to OpenShift using a service account
token. Create a dedicated service account with the minimum required permissions.

```bash
oc create serviceaccount myss-deployer -n myss-${ENV}

oc create role myss-deploy-role \
  --verb=get,list,watch,update,patch \
  --resource=deployments,replicasets,pods \
  -n myss-${ENV}

oc create rolebinding myss-deploy-binding \
  --role=myss-deploy-role \
  --serviceaccount=myss-${ENV}:myss-deployer \
  -n myss-${ENV}
```

Extract the token for use as the `OPENSHIFT_TOKEN` GitHub secret:

```bash
oc create token myss-deployer --duration=8760h -n myss-${ENV}
```

Store this in GitHub → Settings → Secrets → `OPENSHIFT_TOKEN`.

### Application service account

The running pods do not need special cluster permissions. The default service account
is sufficient. No additional role bindings are required for normal operation.

---

## 7. Verify the Project

```bash
oc get all -n myss-${ENV}       # should be empty at this point
oc get quota -n myss-${ENV}
oc get networkpolicy -n myss-${ENV}
oc get secret ghcr-pull-secret -n myss-${ENV}
oc get serviceaccount myss-deployer -n myss-${ENV}
```

---

## Next Steps

Complete the environment setup in this order:

1. **[Vault integration](./vault-integration.md)** — provision secrets before any workload starts
2. **[PVC provisioning](./pvc-provisioning.md)** — create persistent volumes for PostgreSQL and Redis
3. **[Database initialization](./database-initialization.md)** — deploy PostgreSQL and run migrations
4. **[GitHub Actions setup](./github-actions-setup.md)** — configure CI/CD to deploy to this namespace

Once all four guides are complete, apply all remaining manifests:

```bash
oc apply -f openshift/ -n myss-${ENV}
```

Then verify the rollout:

```bash
oc rollout status deployment/myss-postgres -n myss-${ENV}
oc rollout status deployment/myss-redis -n myss-${ENV}
oc rollout status deployment/myss-api -n myss-${ENV}
oc rollout status deployment/myss-frontend -n myss-${ENV}
oc rollout status deployment/myss-celery -n myss-${ENV}
```
