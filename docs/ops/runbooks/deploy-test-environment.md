# Runbook: Deploy myss to the OpenShift test namespace with mock auth

> **Scope:** Brings up a self-contained test deployment of myss-api + myss-web
> in the `myss-test` OpenShift namespace, with mock ICM clients and mock
> authentication (four seeded personas). Production manifests are not touched.

## Preconditions

Application deployers typically do **not** have cluster-admin or project-creator
rights. The namespace-scoped steps below all work with the `admin` RoleBinding
in `myss-test`. The one-time cluster-scoped setup is owned by the platform team.

**Platform team (one-time, before deployer can proceed):**
- Create the `myss-test` namespace with the standard MySS labels
  (see `docs/ops/setup/openshift-project-setup.md` §1–§3).
- Apply the default-deny `NetworkPolicy` baseline (§5c of the same doc).
- Grant the deployer the `admin` RoleBinding in `myss-test`.
- Confirm back to the deployer: "namespace is ready."

**Deployer (everything after handoff):**
- `oc` (or `kubectl`) authenticated to the cluster.
- `oc project myss-test` succeeds (namespace exists and you have access to it).
  If it fails, stop and file a ticket with the platform team — **do not** attempt
  `oc new-project`, which requires `self-provisioner`.
- Required Secrets exist in `myss-test`:
    - `myss-db-secret` — DATABASE_URL, JWT_SECRET
    - `myss-redis-secret` — REDIS_URL
    - `myss-auth-secret` — AUTH_SECRET
  (Apply from `openshift/secrets-template.yaml` of each repo, filling in values.
  Secret creation is namespace-scoped and allowed by the `admin` role.)

## Step 1 — Apply the API test overlay

From the `myss-api` repo:

    oc apply -k openshift/overlays/test/ --load-restrictor=LoadRestrictionsNone

The `--load-restrictor=LoadRestrictionsNone` flag is needed because the
overlay's `resources:` list references files in the parent directory
(see comment in `openshift/overlays/test/kustomization.yaml`).

This creates in `myss-test`:
- Postgres + Redis + API + Celery Deployments (base manifests)
- `myss-api-config` ConfigMap with `ICM_BASE_URL=""` and `ENVIRONMENT=test`
- One-shot `myss-alembic` Job (from base)
- One-shot `myss-seed` Job (from overlay)

Wait for both Jobs to succeed:

    oc get jobs -n myss-test -w

## Step 2 — Copy JWTs from the seed Job logs

    oc logs -n myss-test job/myss-seed

Scroll to the block labelled `myss-web .env (paste into myss-web/.env):` —
the four lines look like:

    MOCK_AUTH_TOKEN_ALICE=eyJhbGciOi...
    MOCK_AUTH_TOKEN_BOB=eyJhbGciOi...
    MOCK_AUTH_TOKEN_CAROL=eyJhbGciOi...
    MOCK_AUTH_TOKEN_WORKER=eyJhbGciOi...

These JWTs are valid for 90 days (controlled by `SEED_TOKEN_TTL_DAYS` on
the seed Job). Re-run the Job to refresh.

## Step 3 — Create the mock-auth-tokens Secret

From the `myss-web` repo, open
`openshift/overlays/test/mock-auth-tokens-secret.yaml` and paste each JWT
in place of its `PASTE_JWT_FROM_myss-seed_JOB_LOGS` placeholder. Do NOT
commit the filled-in file. Then apply:

    oc apply -n myss-test -f openshift/overlays/test/mock-auth-tokens-secret.yaml

Or, faster, use `oc create secret`:

    oc create secret generic mock-auth-tokens -n myss-test \
        --from-literal=MOCK_AUTH_TOKEN_ALICE="$TOKEN_ALICE" \
        --from-literal=MOCK_AUTH_TOKEN_BOB="$TOKEN_BOB" \
        --from-literal=MOCK_AUTH_TOKEN_CAROL="$TOKEN_CAROL" \
        --from-literal=MOCK_AUTH_TOKEN_WORKER="$TOKEN_WORKER" \
        --dry-run=client -o yaml | oc apply -f -

## Step 4 — Apply the frontend test overlay

From the `myss-web` repo:

    oc apply -k openshift/overlays/test/ --load-restrictor=LoadRestrictionsNone

This patches `myss-frontend-config` with the mock-auth flags and wires
`mock-auth-tokens` into the Deployment's `envFrom`.

## Step 5 — Verify

Wait for the frontend pod to be Ready, then curl its health endpoint:

    oc get pods -n myss-test -l component=frontend
    oc port-forward -n myss-test svc/myss-frontend 3000:3000
    curl http://localhost:3000/health

Check the pod logs — you should see exactly one line at startup:

    [auth] mock-auth active: all three locks set; mock auth active

If instead you see "real Auth.js active — mock gate closed: ...", the
gate rejected one of the locks. Check `PUBLIC_ALLOW_MOCK_AUTH`,
`PUBLIC_ENVIRONMENT_NAME`, and `MOCK_AUTH` values against the gate logic
in `src/lib/server/mock-auth-gate.ts`.

Browse to the frontend Route and use the DevPersonaSwitcher (bottom-right
floating toolbar) to switch between personas.

## Rollback

    oc delete -k openshift/overlays/test/ --load-restrictor=LoadRestrictionsNone # from each repo

Keeps Secrets by default; add `--selector='app=myss'` to scope, or
`oc delete namespace myss-test` for a full wipe.

## Refresh tokens (after 90 days)

    oc delete job/myss-seed -n myss-test
    oc apply -k openshift/overlays/test/ --load-restrictor=LoadRestrictionsNone # from myss-api — re-creates seed Job
    # Wait for job to complete, then repeat Steps 2-3 to update the Secret
    oc rollout restart deployment/myss-frontend -n myss-test
