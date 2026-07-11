# Batch pipelines as Cloud Run Jobs (run-to-completion). Scheduler triggers
# them via the Jobs execution API (see scheduler.tf).

resource "google_cloud_run_v2_job" "ingest" {
  name                = "ingest-monarch"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.ingest.email
      timeout         = "1800s"
      max_retries     = 1

      containers {
        image = local.image["ingest-monarch"]
        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_job" "dbt" {
  name                = "dbt-build"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.dbt.email
      timeout         = "1800s"
      max_retries     = 1

      containers {
        image = local.image["dbt-build"]
        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_job" "split" {
  name                = "split-transactions"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.split.email
      timeout         = "900s"
      max_retries     = 1

      containers {
        image = local.image["split-transactions"]
        dynamic "env" {
          for_each = merge(local.common_env, { SPLIT_DRY_RUN = "false" })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}
