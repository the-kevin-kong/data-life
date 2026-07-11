# Each schedule POSTs to the Cloud Run Jobs execution API with the scheduler
# SA's OAuth token. Staggered times run ingest -> dbt -> split in order.

locals {
  run_jobs_api = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs"

  scheduled_jobs = {
    ingest = { job = google_cloud_run_v2_job.ingest.name, cron = var.ingest_schedule }
    dbt    = { job = google_cloud_run_v2_job.dbt.name, cron = var.dbt_schedule }
    split  = { job = google_cloud_run_v2_job.split.name, cron = var.split_schedule }
  }
}

resource "google_cloud_scheduler_job" "jobs" {
  for_each  = local.scheduled_jobs
  name      = "run-${each.value.job}"
  schedule  = each.value.cron
  time_zone = var.scheduler_timezone
  region    = var.region

  http_target {
    http_method = "POST"
    uri         = "${local.run_jobs_api}/${each.value.job}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job.ingest,
    google_cloud_run_v2_job.dbt,
    google_cloud_run_v2_job.split,
    google_project_service.apis,
  ]
}
