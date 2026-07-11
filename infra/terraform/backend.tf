# Remote state in GCS. The bucket name is supplied at init time (partial
# backend config) so the project id stays out of the repo. Create it once:
#
#   gcloud storage buckets create gs://$GCP_PROJECT_ID-tfstate \
#     --project=$GCP_PROJECT_ID --location=us-central1 --uniform-bucket-level-access
#
# Then:  terraform init -backend-config="bucket=$GCP_PROJECT_ID-tfstate"
terraform {
  backend "gcs" {
    prefix = "terraform/state"
  }
}
