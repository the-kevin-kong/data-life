provider "google" {
  project = var.project_id
  region  = var.region

  # Run Terraform as a dedicated deployer service account instead of your
  # personal ADC identity (avoids account conflicts). Prefer setting the
  # GOOGLE_IMPERSONATE_SERVICE_ACCOUNT env var, which impersonates for BOTH
  # this provider AND the GCS state backend; this variable is a provider-only
  # fallback. Your ADC identity needs roles/iam.serviceAccountTokenCreator on
  # the target SA. Empty/unset => authenticate as ADC directly.
  impersonate_service_account = var.impersonate_service_account != "" ? var.impersonate_service_account : null
}

# Enable the APIs the platform needs. Kept on destroy so teardown is clean.
resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

locals {
  # Container image URIs in Artifact Registry.
  image = {
    "ingest-monarch"     = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/ingest-monarch:${var.image_tag}"
    "dbt-build"          = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/dbt-build:${var.image_tag}"
    "split-transactions" = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/split-transactions:${var.image_tag}"
  }

  # Config (non-secret) injected into every job's environment.
  common_env = {
    GCP_PROJECT_ID     = var.project_id
    GCP_REGION         = var.region
    BQ_STAGING_DATASET = var.staging_dataset
    BQ_MARTS_DATASET   = var.marts_dataset
    LOG_JSON           = "true"
  }
}
