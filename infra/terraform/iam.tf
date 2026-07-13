# ---------------------------------------------------------------------------
# Runtime service accounts (one per workload, least privilege).
# ---------------------------------------------------------------------------
resource "google_service_account" "ingest" {
  account_id   = "ingest-monarch"
  display_name = "Monarch ingestion job"
}

resource "google_service_account" "dbt" {
  account_id   = "dbt-build"
  display_name = "dbt build job"
}

resource "google_service_account" "split" {
  account_id   = "split-transactions"
  display_name = "Transaction splitter job"
}

resource "google_service_account" "streamlit" {
  account_id   = "streamlit"
  display_name = "Streamlit dashboard (read-only marts)"
}

resource "google_service_account" "scheduler" {
  account_id   = "scheduler-runner"
  display_name = "Cloud Scheduler -> Cloud Run Jobs invoker"
}

# ---------------------------------------------------------------------------
# BigQuery: jobUser is project-level (needed to run query jobs); dataset-level
# data access is granted in bigquery.tf.
# ---------------------------------------------------------------------------
resource "google_project_iam_member" "job_users" {
  for_each = {
    ingest    = google_service_account.ingest.email
    dbt       = google_service_account.dbt.email
    streamlit = google_service_account.streamlit.email
  }
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "session_user" {
  project = var.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

# Ingestion creates + writes its own dataset (`monarch`) at runtime, so it needs
# project-level data-editor (includes datasets.create).
resource "google_project_iam_member" "ingest_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.ingest.email}"
}

# dbt reads the runtime-created `monarch` dataset (staging/marts writes are
# granted dataset-level in bigquery.tf).
resource "google_project_iam_member" "dbt_bq_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

# ---------------------------------------------------------------------------
# Secret Manager access for the workloads that talk to Monarch.
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret_iam_member" "ingest_accessor" {
  for_each  = google_secret_manager_secret.monarch
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_secret_manager_secret_iam_member" "split_accessor" {
  for_each  = google_secret_manager_secret.monarch
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.split.email}"
}

# Persisting the refreshed session blob requires adding new versions.
resource "google_secret_manager_secret_iam_member" "ingest_session_adder" {
  secret_id = google_secret_manager_secret.monarch["monarch-session"].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_secret_manager_secret_iam_member" "split_session_adder" {
  secret_id = google_secret_manager_secret.monarch["monarch-session"].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.split.email}"
}

# ---------------------------------------------------------------------------
# Let the NAS pull the private dashboard image. The streamlit SA key already
# lives on the NAS for BigQuery; reusing it as the Artifact Registry puller
# (via a Portainer custom registry) avoids a second credential.
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository_iam_member" "streamlit_puller" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.streamlit.email}"
}

# ---------------------------------------------------------------------------
# Let the scheduler SA execute each job. roles/run.invoker includes the
# run.jobs.run permission used by the Jobs execution API.
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_job_iam_member" "scheduler_invokers" {
  for_each = {
    ingest = google_cloud_run_v2_job.ingest.name
    dbt    = google_cloud_run_v2_job.dbt.name
    split  = google_cloud_run_v2_job.split.name
  }
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
