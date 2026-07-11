# Dashboard

Streamlit app over the BigQuery `marts` dataset.

## Local

```bash
gcloud auth application-default login
uv run --package dashboard streamlit run apps/dashboard/src/dl_dashboard/app.py
```

## Deploy on the NAS

Fully automated. On push to `main` (dashboard-relevant paths),
[`.github/workflows/deploy-dashboard.yml`](../../.github/workflows/deploy-dashboard.yml):

1. builds + pushes the image to Artifact Registry (`.../data-life/streamlit:<sha>`), then
2. renders `streamlit.yml` (image pinned to that sha) and pushes it to the
   `the-kevin-kong/docker-compose` repo, where **Portainer GitOps** redeploys the stack.

One-time setup:

1. Terraform provisions the read-only BigQuery service account `streamlit@…`
   (`roles/bigquery.dataViewer` on `marts` + `roles/bigquery.jobUser`, plus
   `roles/artifactregistry.reader` so the NAS can pull the private image). Download its key
   and place it on the NAS; point the Portainer stack's `DASHBOARD_SA_KEY` env at that path.
2. In Portainer, register the Artifact Registry as a custom registry (user `_json_key`,
   password = the SA-key JSON) so it can pull the image.
3. Create the Portainer GitOps stack from `streamlit.yml`; set env `GCP_PROJECT_ID`,
   `GCP_REGION`, `DASHBOARD_SA_KEY`.
4. Point a Cloudflare tunnel public hostname at `http://localhost:8501`. cloudflared runs on
   the host network, so it reaches the dashboard via the published host port (`8501:8501`).
   Consider Cloudflare Access for auth.
