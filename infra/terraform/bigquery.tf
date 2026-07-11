# NOTE: the source dataset (`monarch`) is created at runtime by the ingestion
# service, not here. Its data access is granted project-level in iam.tf.

resource "google_bigquery_dataset" "staging" {
  dataset_id  = var.staging_dataset
  location    = var.bq_location
  description = "dbt staging views."
  depends_on  = [google_project_service.apis]
}

resource "google_bigquery_dataset" "marts" {
  dataset_id  = var.marts_dataset
  location    = var.bq_location
  description = "dbt marts consumed by the dashboard."
  depends_on  = [google_project_service.apis]
}

# --- Dataset-level access (least privilege) --------------------------------
# dbt writes staging + marts. It reads the runtime-created `monarch` dataset
# via a project-level dataViewer grant in iam.tf.
resource "google_bigquery_dataset_iam_member" "dbt_staging_editor" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_marts_editor" {
  dataset_id = google_bigquery_dataset.marts.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

# Dashboard reads marts only.
resource "google_bigquery_dataset_iam_member" "dashboard_marts_viewer" {
  dataset_id = google_bigquery_dataset.marts.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.streamlit.email}"
}
