resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.artifact_repo
  format        = "DOCKER"
  description   = "Container images for data-life Cloud Run jobs."
  depends_on    = [google_project_service.apis]
}
