# ---------------------------------------------------------------------------
# Keyless CI deploys: a Workload Identity Federation pool/provider for GitHub
# Actions, plus a dedicated deployer service account the workflows impersonate.
# No service-account keys are ever created. Feeds the repo's Actions config:
#   secrets.WIF_PROVIDER = output github_actions.WIF_PROVIDER
#   secrets.DEPLOY_SA    = output github_actions.DEPLOY_SA
# See .github/workflows/deploy.yml and deploy-dashboard.yml.
# ---------------------------------------------------------------------------

locals {
  github_owner = split("/", var.github_repo)[0]
}

# Least-privilege CI identity: push images + update Cloud Run jobs only.
resource "google_service_account" "github_deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions deployer (WIF, keyless)"
}

# --- Workload Identity Federation: trust GitHub's OIDC tokens ---------------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  # Google requires a condition on repo-scoped providers; pin to this owner so
  # only tokens from the org can even attempt an exchange.
  attribute_condition = "assertion.repository_owner == '${local.github_owner}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Only this repo may impersonate the deployer SA.
resource "google_service_account_iam_member" "github_deployer_wif" {
  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# --- What the deployer may do ----------------------------------------------
# Push images to the Artifact Registry repo (both deploy paths).
resource "google_artifact_registry_repository_iam_member" "github_deployer_push" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Update each Cloud Run job's image (deploy.yml `gcloud run jobs update`).
resource "google_cloud_run_v2_job_iam_member" "github_deployer_run" {
  for_each = {
    ingest = google_cloud_run_v2_job.ingest.name
    dbt    = google_cloud_run_v2_job.dbt.name
    split  = google_cloud_run_v2_job.split.name
  }
  location = var.region
  name     = each.value
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.github_deployer.email}"
}

# actAs the runtime SAs the jobs run as (required to update a job bound to them).
resource "google_service_account_iam_member" "github_deployer_actas" {
  for_each = {
    ingest = google_service_account.ingest.name
    dbt    = google_service_account.dbt.name
    split  = google_service_account.split.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}
