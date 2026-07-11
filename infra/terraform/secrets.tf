# Secret containers are created empty. Add values out-of-band, e.g.:
#
#   printf '%s' 'me@example.com'  | gcloud secrets versions add monarch-email      --data-file=-
#   printf '%s' 'app-password'    | gcloud secrets versions add monarch-password   --data-file=-
#   printf '%s' 'TOTP_SEED'       | gcloud secrets versions add monarch-mfa-secret --data-file=-
#
# `monarch-session` is populated automatically by the first ingestion run.
resource "google_secret_manager_secret" "monarch" {
  for_each  = toset(var.monarch_secret_ids)
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}
