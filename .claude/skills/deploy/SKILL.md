---
name: deploy
description: Deployment runbook for data-life — the two paths (Cloud Run jobs via WIF, and the Streamlit dashboard via Portainer GitOps), their triggers, required GH vars/secrets, and how to verify. Use when asked to deploy, release, ship the jobs or dashboard, or set up the deploy pipeline.
---

# deploy — runbook

Two independent paths. Both build images to Artifact Registry (repo `data-life`) using **keyless
Workload Identity Federation** — no long-lived keys.

## Path 1 — Cloud Run jobs (ingest / dbt-build / split)

Workflow: [.github/workflows/deploy.yml](../../../.github/workflows/deploy.yml). Trigger:
**`workflow_dispatch`** (manual, Actions tab).

- `build` job: matrix over `ingest-monarch`, `dbt-build`, `split-transactions`; builds each
  Dockerfile, pushes `<region>-docker.pkg.dev/<project>/<ARTIFACT_REPO>/<name>:<sha>` + `:latest`.
- `deploy` job: `gcloud run jobs update <name> --region <region> --image ...:<sha>`.
- Requires repo **vars** `GCP_PROJECT_ID`, `GCP_REGION`, `ARTIFACT_REPO`; **secrets**
  `WIF_PROVIDER`, `DEPLOY_SA`.
- Scheduling is Terraform-managed (Cloud Scheduler → Jobs execution API), staggered
  ingest → dbt → split. Deploying only updates the image the schedule runs.

Local alternative: `just cloud-build` (Cloud Build builds all four images, incl. `streamlit`).

## Path 2 — Streamlit dashboard (Portainer GitOps)

Workflow: [.github/workflows/deploy-dashboard.yml](../../../.github/workflows/deploy-dashboard.yml).
Trigger: **push to `main`** touching `apps/dashboard/**`, `packages/common/**`, `uv.lock`,
`pyproject.toml`, or the workflow itself; also `workflow_dispatch`.

- `build` job: builds [apps/dashboard/Dockerfile](../../../apps/dashboard/Dockerfile), pushes
  `.../<ARTIFACT_REPO>/streamlit:<sha>` + `:latest`.
- `deploy` job: checks out this repo + the compose repo (`vars.COMPOSE_REPO`, token
  `secrets.DOCKER_COMPOSE_PAT`), runs
  `sed "s/__IMAGE_TAG__/<sha>/" apps/dashboard/streamlit.yml > docker-compose/streamlit.yml`,
  commits + pushes if changed.
- **Portainer GitOps** on the NAS watches that repo and redeploys. The **immutable git-sha image
  tag** is the mechanism: rewriting it changes the compose file, so Portainer sees a diff and
  pulls the new image. Template: [apps/dashboard/streamlit.yml](../../../apps/dashboard/streamlit.yml).
- Extra config for this path: **vars** `COMPOSE_REPO`; **secret** `DOCKER_COMPOSE_PAT`
  (fine-grained PAT, `contents:write` on the compose repo). The NAS pulls the private image via a
  Portainer custom registry (`_json_key` + the streamlit SA key, which also has
  `roles/artifactregistry.reader`).

## Verify a deploy

1. Actions run is green (both jobs).
2. Image present: `gcloud artifacts docker images list
   <region>-docker.pkg.dev/<project>/data-life/<name>` shows the new `:<sha>`.
3. Jobs path: `gcloud run jobs describe <name> --region <region>` points at the new image.
4. Dashboard path: the `docker-compose` repo has the auto-commit; Portainer redeploys; the
   dashboard loads and renders marts data.

## Notes

- Never commit secrets or the project id — everything sensitive is a GH var/secret, WIF, or NAS
  stack env (see CLAUDE.md → Safety). Project id is never hardcoded.
- Infra changes (new job, IAM, schedule) go through Terraform (`just tf-plan` / `tf-apply`), not
  these workflows.
