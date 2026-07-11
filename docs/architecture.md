# Architecture

## Goals

1. **Ingest** financial data from Monarch Money into a private data warehouse.
2. **Transform** it into clean, queryable analytics models.
3. **Report** on it via a self-hosted dashboard.
4. **Automate transaction splitting**: find transactions tagged in Monarch and
   split them into predetermined legs, pushing the splits back via the API.

The repository is public (portfolio); all data and credentials are private.

## System overview

```
                         ┌──────────────────────────── GCP project ($GCP_PROJECT_ID) ───────────────────┐
                         │                                                                               │
 Cloud Scheduler ──cron──┼─► Cloud Run: ingest-monarch ──► BigQuery raw.*  (MERGE-upsert + soft-delete)  │
                         │                                        │                                      │
                    ──cron──► Cloud Run: dbt build ─────────► BigQuery staging.* ─► marts.*              │
                         │                                        ▲                                      │
                    ──cron──► Cloud Run: split-transactions ──┐   │                                      │
                         │        │  reads/writes Monarch     │   │                                      │
                         │   Secret Manager (creds, TOTP, session)│                                      │
                         └────────┼───────────────────────────────┼──────────────────────────────────── ┘
                                  ▼                                │ read-only SA
                            Monarch Money API              Streamlit (NAS/Docker) ─► SWAG+Cloudflare ─► web
```

## Components

### Ingestion (`services/ingest-monarch`)
- Runs on Cloud Run, triggered daily by Cloud Scheduler.
- Uses `dl_monarch` to authenticate (session reused from Secret Manager; falls
  back to `login(mfa_secret_key=...)` with a persisted refresh).
- Pulls the **full** set of transactions, accounts, categories, tags, budgets.
- Loads each entity to BigQuery via `dl_common`'s **MERGE-upsert**:
  - matched → update payload, refresh `_updated_at`, clear `_is_deleted`
  - not matched by target → insert, stamp `_ingested_at`
  - **not matched by source → soft-delete** (`_is_deleted=true`, `_deleted_at`)
- Net effect: one row per record (low storage) and deletions are observable.

### Transforms (`transform/dbt`)
- dbt Core v2.0 (Fusion) project; BigQuery adapter is built into Fusion. Sources point at `raw.*`.
- `staging` views: dedupe/type, filter `where not _is_deleted`.
- `marts`: `fct_transactions`, `dim_accounts`, `dim_categories`, and spending /
  cashflow summaries the dashboard reads.
- Ships dbt tests (not_null/unique/relationships) and generated docs.
- Deployed as a container that runs `dbt build`, chained after ingestion.

### Splitter (`services/split-transactions`)
- Tag-driven: you apply a tag like `split:rent` to a transaction in Monarch.
- A YAML rule config maps each tag to a set of **legs**. A leg is a fixed
  dollar amount or a percentage; an optional remainder leg absorbs rounding so
  the legs always sum exactly to the transaction total.
- Idempotent: transactions already split or tagged `split:done` are skipped;
  successful splits get tagged `split:done`.
- `--dry-run` prints the planned legs without writing.

### Dashboard (`apps/dashboard`)
- Streamlit reading `marts` through a read-only BigQuery service account.
- Containerized; the image is built + pushed to Artifact Registry on merge to `main`, and a
  generated `streamlit.yml` is pushed to the `docker-compose` repo where Portainer GitOps
  redeploys it on the NAS. Publishes port 8501 on the host; the host-network cloudflared
  container reaches it at `http://localhost:8501` and the Cloudflare tunnel handles TLS +
  public access.

## Authentication & secrets

- `monarch-email`, `monarch-password`, `monarch-mfa-secret` (TOTP seed) and
  `monarch-session` (persisted blob) live in Secret Manager.
- Session lifecycle: load persisted session → if invalid, `login()` with the
  TOTP seed → persist the refreshed session. Scheduled runs never prompt for MFA.
- Local dev uses Application Default Credentials (`gcloud auth
  application-default login`). No service-account key files.

## Infrastructure (`infra/terraform`)

Terraform manages: BigQuery datasets (`staging`, `marts` — the `monarch` source
dataset is created by the ingestion service), Artifact
Registry, Secret Manager secrets (created empty), per-service runtime service
accounts + least-privilege IAM, Cloud Run services, and Cloud Scheduler jobs.
State is stored in a GCS bucket.

## Cost

At personal data volume everything sits inside GCP free tiers (BigQuery storage
+ query, Cloud Run, 3 free Scheduler jobs). Secret Manager cost is negligible.
The dashboard runs on the existing NAS at no marginal cloud cost.
