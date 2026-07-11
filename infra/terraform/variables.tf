variable "project_id" {
  type        = string
  description = "GCP project id. Set GCP_PROJECT_ID; the justfile bridges it to TF_VAR_project_id (Terraform only auto-binds TF_VAR_* env vars). No default so the id is never committed."
}

variable "impersonate_service_account" {
  type    = string
  default = ""
  # Provider-only fallback. Prefer the GOOGLE_IMPERSONATE_SERVICE_ACCOUNT env
  # var, which impersonates for both the provider and the GCS state backend.
  description = "Optional deployer SA email for the provider to impersonate. Empty = use ADC directly."
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "staging_dataset" {
  type    = string
  default = "staging"
}

variable "marts_dataset" {
  type    = string
  default = "marts"
}

variable "artifact_repo" {
  type    = string
  default = "data-life"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "scheduler_timezone" {
  type    = string
  default = "America/New_York"
}

# Cron schedules (Scheduler runs jobs in this order via staggered times).
variable "ingest_schedule" {
  type    = string
  default = "0 5 * * *" # 05:00 daily
}

variable "dbt_schedule" {
  type    = string
  default = "30 5 * * *" # 05:30 daily, after ingestion
}

variable "split_schedule" {
  type    = string
  default = "0 6 * * *" # 06:00 daily
}

variable "monarch_secret_ids" {
  type    = list(string)
  default = ["monarch-email", "monarch-password", "monarch-mfa-secret", "monarch-session"]
}

variable "github_repo" {
  type        = string
  default     = "the-kevin-kong/data-life"
  description = "owner/repo whose GitHub Actions may impersonate the deployer SA via WIF."
}
