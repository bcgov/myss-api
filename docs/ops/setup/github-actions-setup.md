# GitHub Actions Setup

**Audience:** Developer or ops engineer configuring CI/CD for a new environment or repository.
**Read time:** ~20 minutes.
**When to use:** Initial repository setup or when adding a new deployment target.

---

## Overview

The repository has two workflows:

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | Push to any branch; PR to `main` | Lint, type-check, and test |
| `.github/workflows/deploy.yml` | Push to `main` | Build images, push to ghcr.io, deploy to OpenShift |

---

## 1. Required GitHub Repository Secrets

These secrets must be set in **GitHub → repository → Settings → Secrets and variables → Actions**.

### Secrets used by `deploy.yml`

| Secret name | Description | How to obtain |
|---|---|---|
| `OPENSHIFT_SERVER` | OpenShift API server URL, e.g. `https://api.<cluster>.devops.gov.bc.ca:6443` | From cluster operator or `oc whoami --show-server` |
| `OPENSHIFT_TOKEN` | Service account token for the `myss-deployer` SA | See [openshift-project-setup.md §6](./openshift-project-setup.md) |
| `OPENSHIFT_NAMESPACE` | Target namespace, e.g. `myss-dev1` | The namespace created in [openshift-project-setup.md](./openshift-project-setup.md) |

**Note:** `GITHUB_TOKEN` is provided automatically by GitHub Actions and is used to
authenticate against `ghcr.io`. No manual configuration is required for image publishing.

### Secrets NOT needed (automatically available)

| Variable | Source |
|---|---|
| `GITHUB_TOKEN` | Injected by GitHub Actions runtime — authenticates `docker/login-action` to `ghcr.io` |
| `github.sha` | Git commit SHA — used as the image tag |
| `github.repository` | Repository path — used to build the image name |

---

## 2. CI Pipeline (`ci.yml`)

The CI workflow runs 4 parallel jobs on every push and on pull requests to `main`.
All 4 jobs must pass before a PR can be merged.

### Job: `api-lint` — API Lint and Type Check

Working directory: `myss-api`

```
pip install -e ".[dev]"
ruff check .
mypy app/
```

Runs `ruff` for linting/formatting and `mypy` for static type checking.
Python version: 3.12.

### Job: `api-test` — API pytest

Working directory: `myss-api`

```
pip install -e ".[dev]"
python -m pytest -v --tb=short
```

Runs the full test suite with verbose output and short tracebacks.
Python version: 3.12.

### Job: `web-lint` — Web Lint and Type Check

Working directory: `myss-web`

```
npm ci
npm run check
```

Runs `svelte-check` for TypeScript and Svelte type checking.
Node version: 20. Uses `package-lock.json` for reproducible installs.

### Job: `web-test` — Web Vitest

Working directory: `myss-web`

```
npm ci
npm test
```

Runs the Vitest unit test suite.
Node version: 20.

---

## 3. Deploy Pipeline (`deploy.yml`)

The deploy workflow runs only on pushes to `main`. It has two sequential jobs.

### Job 1: `build-and-push` — Build and Push Docker Images

**Permissions:** `contents: read`, `packages: write` (write is needed to push to ghcr.io).

**Image names** (from `deploy.yml` env block):

```
ghcr.io/<org>/<repo>/myss-api:<git-sha>
ghcr.io/<org>/<repo>/myss-api:latest
ghcr.io/<org>/<repo>/myss-frontend:<git-sha>
ghcr.io/<org>/<repo>/myss-frontend:latest
```

Both `:<git-sha>` (immutable, for deploy) and `:latest` (mutable, for convenience)
are pushed on every merge to `main`.

Build contexts:
- API: `./myss-api`
- Frontend: `./myss-web`

### Job 2: `deploy` — Deploy to OpenShift

**Depends on:** `build-and-push` (must succeed first).
**Environment:** `production` (GitHub environment, triggers approval gate — see §5 below).

Steps:

1. Install `oc` CLI via `redhat-actions/openshift-tools-installer@v1`
2. Log in to OpenShift:
   ```
   oc login $OPENSHIFT_SERVER --token=$OPENSHIFT_TOKEN
   ```
   TLS verification is enabled (`--insecure-skip-tls-verify=false`).
3. Update image tags on both deployments:
   ```
   oc set image deployment/myss-api myss-api=<registry>/<image>:<sha> -n $OPENSHIFT_NAMESPACE
   oc set image deployment/myss-frontend myss-frontend=<registry>/<image>:<sha> -n $OPENSHIFT_NAMESPACE
   ```
4. Wait for rollout:
   ```
   oc rollout status deployment/myss-api -n $OPENSHIFT_NAMESPACE --timeout=5m
   oc rollout status deployment/myss-frontend -n $OPENSHIFT_NAMESPACE --timeout=5m
   ```

The rollout wait step means the workflow fails if pods do not become healthy within
5 minutes, giving a clear failure signal in the GitHub UI.

---

## 4. Branch Protection Rules

Configure these in **GitHub → repository → Settings → Branches → Add rule** for the `main` branch.

| Rule | Setting |
|---|---|
| Require status checks to pass | Enable |
| Required status checks | `API — Lint & Type Check`, `API — pytest`, `Web — Lint & Type Check`, `Web — Vitest` |
| Require branches to be up to date | Enable |
| Require pull request reviews | Enable |
| Required approvals | 1 (minimum) |
| Dismiss stale reviews | Enable |
| Restrict pushes to matching branches | Enable (no direct pushes to `main`) |
| Do not allow bypass | Enable for all roles except admins |

---

## 5. Deployment Approval Gates for Production

The `deploy` job uses `environment: production`. GitHub Environments can require
manual approval before the job runs.

Configure in **GitHub → repository → Settings → Environments → production**:

| Setting | Value |
|---|---|
| Required reviewers | Add at least one senior developer or ops engineer |
| Wait timer | Optional — set 0 for immediate approval capability |
| Deployment branches | Restrict to `main` branch only |

When a merge to `main` triggers the workflow, the `build-and-push` job runs
automatically. The `deploy` job then pauses and sends a notification to required
reviewers. A reviewer must approve in the GitHub UI before the deployment proceeds.

For non-production environments (`dev1`, `test1`, etc.), consider creating separate
GitHub Environments without required reviewers so deployments are fully automatic.

---

## 6. Adding a New Deployment Target

To deploy to an additional OpenShift namespace (e.g. `myss-test1`):

1. Create the project and `myss-deployer` service account (see [openshift-project-setup.md](./openshift-project-setup.md))
2. Create a new GitHub Environment: `test1`
3. Add secrets scoped to that environment: `OPENSHIFT_SERVER`, `OPENSHIFT_TOKEN`, `OPENSHIFT_NAMESPACE`
4. Add a new job to `deploy.yml` that targets the `test1` environment (copy the `deploy` job, change `environment:` and which secrets are referenced)

---

## 7. Verifying the Setup

After adding secrets and pushing a commit to `main`:

1. Open **Actions** tab — confirm the `CI` workflow shows 4 green jobs
2. Confirm the `Deploy` workflow triggers after CI completes
3. Check `build-and-push` job logs — look for "Pushed" confirmation for both images
4. Check `deploy` job logs — look for `successfully rolled out` from `oc rollout status`

If the `deploy` job fails at OpenShift login, verify `OPENSHIFT_TOKEN` has not expired
and the service account still exists in the namespace.
