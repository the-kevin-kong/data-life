output "artifact_registry_repo" {
  description = "Docker repo to push images to."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}"
}

output "service_accounts" {
  description = "Runtime service account emails."
  value = {
    ingest    = google_service_account.ingest.email
    dbt       = google_service_account.dbt.email
    split     = google_service_account.split.email
    streamlit = google_service_account.streamlit.email
    scheduler = google_service_account.scheduler.email
  }
}

output "bigquery_datasets" {
  value = {
    staging = google_bigquery_dataset.staging.dataset_id
    marts   = google_bigquery_dataset.marts.dataset_id
  }
}

output "github_actions" {
  description = "Set these on the data-life repo (Settings → Secrets and variables → Actions) for keyless WIF deploys."
  value = {
    WIF_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    DEPLOY_SA    = google_service_account.github_deployer.email
  }
}
