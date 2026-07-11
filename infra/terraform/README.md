# Infrastructure (Terraform)

Provisions all GCP resources for data-life. The project id is never stored in
the repo — provide it via the `GCP_PROJECT_ID` env var (Terraform reads it as
`TF_VAR_project_id`).

## What it creates
- BigQuery datasets: `staging`, `marts` (+ least-privilege dataset IAM). The
  `monarch` source dataset is created at runtime by the ingestion service.
- Artifact Registry Docker repo `data-life`
- Secret Manager secrets (empty): `monarch-email`, `monarch-password`,
  `monarch-mfa-secret`, `monarch-session`
- Runtime service accounts: ingest / dbt / split / dashboard-reader / scheduler
- Cloud Run **Jobs**: `ingest-monarch`, `dbt-build`, `split-transactions`
- Cloud Scheduler jobs that trigger each Run Job on a cron

## Authentication: deployer service account (impersonation)

Terraform runs as a dedicated **deployer service account**, not your personal
ADC identity — so it can't collide with whatever account `gcloud` happens to be
logged into, and there are **no downloaded key files**. Your ADC identity only
needs permission to mint tokens for that SA.

One-time bootstrap (run once, as a project owner/editor):

```bash
export GCP_PROJECT_ID=your-gcp-project-id
SA="terraform-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com"

# 1. Create the deployer SA
gcloud iam service-accounts create terraform-deployer \
  --project="$GCP_PROJECT_ID" --display-name="Terraform deployer"

# 2. Grant it the roles Terraform needs to provision everything
for ROLE in \
  roles/serviceusage.serviceUsageAdmin \
  roles/resourcemanager.projectIamAdmin \
  roles/iam.serviceAccountAdmin \
  roles/iam.serviceAccountUser \
  roles/bigquery.admin \
  roles/run.admin \
  roles/cloudscheduler.admin \
  roles/secretmanager.admin \
  roles/artifactregistry.admin \
  roles/iam.workloadIdentityPoolAdmin \
  roles/storage.admin ; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None
done

# 3. Let YOUR user impersonate the SA (mint access tokens for it)
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="user:$(gcloud config get-value account)" \
  --role=roles/iam.serviceAccountTokenCreator

# 4. Point Terraform (provider + GCS backend) at the SA
echo "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=$SA" >> ../../.env
```

`GOOGLE_IMPERSONATE_SERVICE_ACCOUNT` is the single knob: it makes both the
google provider and the GCS state backend act as the SA. (A `TF_VAR`-driven
`impersonate_service_account` variable also exists but only affects the
provider, so prefer the env var.) You still run `gcloud auth
application-default login` as yourself to provide the base identity.

## Order of operations

```bash
# Provide the project id via the environment (never committed).
export GCP_PROJECT_ID=your-gcp-project-id
export TF_VAR_project_id="$GCP_PROJECT_ID"

# 0. One-time: bootstrap the deployer SA (above), then create the state bucket.
#    Create the bucket as an identity that can (your user, or the SA).
gcloud storage buckets create gs://$GCP_PROJECT_ID-tfstate \
  --project=$GCP_PROJECT_ID --location=us-central1 --uniform-bucket-level-access

# 1. Init (bucket passed as partial backend config) + apply.
#    With GOOGLE_IMPERSONATE_SERVICE_ACCOUNT set, both run as the deployer SA.
cd infra/terraform
terraform init -backend-config="bucket=$GCP_PROJECT_ID-tfstate"
terraform apply

# 2. Populate secret values (see secrets.tf for the exact commands)
printf '%s' 'me@example.com' | gcloud secrets versions add monarch-email --data-file=-
# ...password, mfa seed...

# 3. Build + push images, then re-apply so jobs pick up :latest
#    (see .github/workflows/deploy.yml or build locally with Cloud Build)
```

> Images must exist in Artifact Registry before the Cloud Run Jobs can execute.
> The Scheduler wiring uses the Jobs execution API with the scheduler SA's
> OAuth token (`roles/run.invoker`).

## GitHub Actions deploy (keyless WIF)

`wif.tf` provisions a Workload Identity Federation pool/provider plus a dedicated
`github-deployer` service account the CI workflows impersonate — no SA keys. It can push
images (`artifactregistry.writer`) and update the three Cloud Run jobs (`run.developer` +
`serviceAccountUser` on the runtime SAs). The trusted repo defaults to
`the-kevin-kong/data-life` (`var.github_repo`).

After `terraform apply`, wire the two Actions secrets from the outputs:

```bash
terraform output github_actions   # → { WIF_PROVIDER = "...", DEPLOY_SA = "..." }

REPO=the-kevin-kong/data-life
gh secret set WIF_PROVIDER -R "$REPO" \
  -b "$(terraform output -json github_actions | jq -r .WIF_PROVIDER)"
gh secret set DEPLOY_SA -R "$REPO" \
  -b "$(terraform output -json github_actions | jq -r .DEPLOY_SA)"
```

Also set the repo **vars** `GCP_PROJECT_ID`, `GCP_REGION`, `ARTIFACT_REPO` (and `COMPOSE_REPO`
for the dashboard). Consumed by [deploy.yml](../../.github/workflows/deploy.yml) and
[deploy-dashboard.yml](../../.github/workflows/deploy-dashboard.yml).

## Notes
- `*.tfvars` and state are git-ignored; only `*.tfvars.example` is committed.
- The `dashboard-reader` SA is created here; generate its key out-of-band
  (`gcloud iam service-accounts keys create`) and place it on the NAS — keys are
  intentionally not managed in Terraform state.
