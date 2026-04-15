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
| `.github/workflows/deploy.yml` | Push to `main` | Build the API image, push to ghcr.io, deploy to OpenShift |

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

## CI workflow (`.github/workflows/ci.yml`)

Two jobs run on every push and pull request:

### `lint`
- Installs dependencies via `pip install -e ".[dev]"`
- Runs `ruff check .`
- Runs `mypy app/`

### `test`
- Installs dependencies via `pip install -e ".[dev]"`
- Runs `python -m pytest -v`

Both jobs block merge via branch protection (see below).

Python version for both jobs: 3.12 (with `pip` cache).

---

## Deploy workflow (`.github/workflows/deploy.yml`)

On every push to `main`, the workflow:

1. Builds the API Docker image using `Dockerfile` at repo root (build context `.`).
2. Pushes to `ghcr.io/<org>/myss-api:${SHA}` and `:latest` via `docker/build-push-action@v5` (permissions: `contents: read`, `packages: write`; authenticated to GHCR with the runtime-provided `GITHUB_TOKEN`).
3. Installs `oc` CLI and logs in to OpenShift (`OPENSHIFT_SERVER` / `OPENSHIFT_TOKEN`, TLS verification enabled).
4. Triggers an `oc set image deployment/myss-api ...` rollout on the target OpenShift namespace (`OPENSHIFT_NAMESPACE`), using the `production` GitHub environment (approval gate — see §5 below).
5. Waits for rollout with `oc rollout status deployment/myss-api --timeout=5m` — the workflow fails if pods are not healthy within 5 minutes, giving a clear failure signal in the GitHub UI.

Promotion to production is manual (see `docs/ops/runbooks/promote-to-prod.md`).

The frontend (`myss-web`) has its own deploy workflow and image
(`ghcr.io/<org>/myss-web`). This workflow does not touch it.

---

## 4. Branch Protection Rules

Configure these in **GitHub → repository → Settings → Branches → Add rule** for the `main` branch.

Required status checks (configure in GitHub Settings → Branches →
Branch protection rules for `main`):

- `lint`
- `test`

| Rule | Setting |
|---|---|
| Require status checks to pass | Enable |
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

1. Open **Actions** tab — confirm the `CI` workflow shows both `lint` and `test` jobs green
2. Confirm the `Deploy` workflow triggers after CI completes
3. Check `build-and-push` job logs — look for "Pushed" confirmation for the API image
4. Check `deploy` job logs — look for `successfully rolled out` from `oc rollout status`

If the `deploy` job fails at OpenShift login, verify `OPENSHIFT_TOKEN` has not expired
and the service account still exists in the namespace.
