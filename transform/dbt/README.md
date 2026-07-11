# dbt: data-life transforms

Transforms raw Monarch data into analytics models on BigQuery. Uses **dbt Core
v2.0 (Fusion)** — the BigQuery adapter is built into Fusion (there is no separate
`dbt-bigquery` v2 package). Fusion is installed via the workspace dev deps, so
`uv run dbt ...` works.

- **Sources** (`models/staging/_sources.yml`) → the `raw.*` tables landed by the
  ingestion job.
- **Staging** (`staging` dataset, views) → typed one-row-per-record models that
  parse the raw JSON and drop soft-deleted rows.
- **Marts** (`marts` dataset, tables) → `fct_transactions`, `dim_accounts`,
  `dim_categories`, and `mart_monthly_spending` (what the dashboard reads).

## Local run

```bash
gcloud auth application-default login
export GCP_PROJECT_ID=your-gcp-project-id
cd transform/dbt
uv run dbt deps
uv run dbt build          # runs + tests everything
uv run dbt docs generate  # optional: browse lineage with `dbt docs serve`
```

`profiles.yml` is committed (no secrets — env-var references + ADC auth). A
`generate_schema_name` macro routes models to the `staging` and `marts`
datasets directly instead of dbt's default `<target>_<schema>` naming.

> JSON field paths in the staging models reflect Monarch's expected shape.
> Verify them against the first live pull and adjust in one place if needed.
