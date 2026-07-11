# CLAUDE.md — data-life

Personal-finance ELT pipeline: **Monarch Money → BigQuery (raw) → dbt (staging/marts) →
Streamlit dashboard**. A `uv`-workspace monorepo. Ingestion and splitting run as scheduled
Cloud Run Jobs; the dashboard runs on a home NAS via Portainer GitOps. Full design in
[docs/architecture.md](docs/architecture.md).

Data flow: `raw monarch.* (MERGE-upsert) → staging views → marts tables → dashboard (marts only)`.

## Workspace layout

`uv` workspace; root `pyproject.toml` is an umbrella depending on every member, so a bare
`uv sync` / `uv run` installs the whole graph. Python `>=3.12,<3.13`.

| Import pkg | Dist / dir | Purpose |
|---|---|---|
| `dl_common` | `dl-common` — [packages/common](packages/common) | Shared base: `Settings`, structlog logging, `BigQueryClient` (MERGE-upsert loader), `SecretManager`. |
| `dl_monarch` | `dl-monarch` — [packages/monarch-client](packages/monarch-client) | Session-persisting typed wrapper over the `monarchmoney` community fork. |
| `dl_ingest` | `ingest-monarch` — [services/ingest-monarch](services/ingest-monarch) | Cloud Run Job: pull Monarch → `monarch.*` raw tables. |
| `dl_splitter` | `split-transactions` — [services/split-transactions](services/split-transactions) | Cloud Run Job: tag-driven transaction splitter (pure Decimal engine). |
| `dl_dashboard` | `dashboard` — [apps/dashboard](apps/dashboard) | Streamlit app over `marts`. |

Not workspace members: [transform/dbt](transform/dbt) (dbt project, run via `uv run dbt`),
[infra/terraform](infra/terraform), [docs](docs).

Naming: import packages use the `dl_` prefix; `dl_common` is imported by everything —
`from dl_common import BigQueryClient, get_logger, get_settings, SecretManager`.

## Commands — use the `justfile`

| Recipe | Does |
|---|---|
| `just setup` | `uv sync --all-packages` + `uvx pre-commit install` |
| `just check` | **The gate**: `lint` → `typecheck` → `test` |
| `just lint` | `uv run ruff check .` + `uv run ruff format --check .` |
| `just fmt` | `uv run ruff check --fix .` + `uv run ruff format .` |
| `just typecheck` | `uv run mypy packages services apps` |
| `just test` | `uv run pytest` |
| `just dbt-parse` / `dbt-build` | `cd transform/dbt && uv run dbt parse` / `build` |
| `just dashboard` | `uv run --package dashboard streamlit run apps/dashboard/src/dl_dashboard/app.py` |
| `just ingest` / `split-dry` / `split` | run the service entrypoints |
| `just tf-plan` / `tf-apply` / `tf-init` | terraform in `infra/terraform` with `TF_VAR_project_id` |
| `just cloud-build` | build+push all images via Cloud Build |

## Quality gate

Run **`just check`** (or the `/check` skill) before proposing a commit; keep it green.
- `mypy` is `strict` (`disallow_untyped_defs`, `warn_unused_ignores`). Third-party libs without
  stubs are in the `ignore_missing_imports` override list in root `pyproject.toml` — add new ones
  there, don't sprinkle `# type: ignore`.
- `ruff`: `line-length = 100`, selects `E,F,I,UP,B,SIM,TID,RUF`; tests may use `assert` (`S101`
  ignored under `**/tests/*`).
- Tests are **pure unit** (no network/GCP): the split engine, generated MERGE SQL, the GraphQL
  extractor. Keep new tests offline. `asyncio_mode = "auto"` (no decorator needed).
- Pre-commit checks the **staged** blob — `git add` your fixes before committing or the hook sees
  the old version.

## Data & config conventions

- **Raw layer = MERGE-upsert + soft-delete.** `BigQueryClient.merge_upsert()`
  ([packages/common/src/dl_common/bigquery.py](packages/common/src/dl_common/bigquery.py)) writes
  one row per source record into `{id, data JSON, _ingested_at, _updated_at, _is_deleted,
  _deleted_at}`; records absent from a pull are flagged `_is_deleted=TRUE`, not dropped. An empty
  pull is a **no-op** (never mass-soft-delete). dbt owns all typing/modeling downstream; the
  dashboard reads `marts` only.
- **Config** via `dl_common.config.Settings` (pydantic-settings, reads env / `.env`), accessed
  through cached `get_settings()`. Key vars + defaults: `GCP_PROJECT_ID=""` (empty on purpose),
  `GCP_REGION=us-central1`, `BQ_STAGING_DATASET=staging`, `BQ_MARTS_DATASET=marts`,
  `SPLIT_DRY_RUN=true`, `LOG_LEVEL=INFO`, `LOG_JSON=false`.
- **Never hardcode the project id.** It lives only in env (`.env` local / Cloud Run env /
  Portainer stack env / GH repo vars) and `env_var('GCP_PROJECT_ID')` in dbt/TF. CI uses the
  placeholder `ci-parse-only`.
- **Logging**: structlog via `dl_common.logging`; `get_logger(__name__)` + structured kwargs
  (`log.info("merge_upsert_done", table=..., rows=...)`), never f-string messages. `LOG_JSON=true`
  in every deployed container.
- **Idempotency**: both jobs re-run safely (ingest via MERGE; splitter via `split:done` tag +
  already-split guards + dry-run default). Entrypoints `sys.exit(1)` on failure so Cloud
  Run/Scheduler records a failed run.

## dbt

dbt-core **v2 (Fusion)** — the BigQuery adapter is built in (no `dbt-bigquery` package); run with
`uv run dbt` from [transform/dbt](transform/dbt). Auth is ADC + `GCP_PROJECT_ID`; profile is
committed (`profiles.yml`, no secrets, `method: oauth`). Naming: `stg_monarch__<entity>` (views in
`staging`), `fct_`/`dim_`/`mart_` (tables in `marts`). Staging parses raw JSON with
`json_value(data,'$.…')` and filters `where not _is_deleted`. `just dbt-parse` is the offline
check (used in CI, no BigQuery). See the `/new-mart` skill to add a model.

## Deploy

Two paths (see the `/deploy` skill):
- **Cloud Run jobs** — [.github/workflows/deploy.yml](.github/workflows/deploy.yml),
  `workflow_dispatch`, keyless via Workload Identity Federation.
- **Dashboard** — [.github/workflows/deploy-dashboard.yml](.github/workflows/deploy-dashboard.yml),
  on push to `main` (dashboard paths); builds a sha-tagged image, rewrites
  [apps/dashboard/streamlit.yml](apps/dashboard/streamlit.yml), pushes it to the `docker-compose`
  repo where **Portainer GitOps** redeploys. The immutable git-sha image tag is the redeploy
  trigger.

## Infra

`just tf-plan` / `tf-apply` (in [infra/terraform](infra/terraform)). Requires a **local
`terraform` binary** (the recipes shell out to bare `terraform` — "command not found" means it
isn't installed), plus `TF_VAR_project_id` (from `GCP_PROJECT_ID`) and
`GOOGLE_IMPERSONATE_SERVICE_ACCOUNT`. GCS backend is partial-configured at init. Always `tf-plan`
before `tf-apply`. Bootstrap details in [infra/terraform/README.md](infra/terraform/README.md).

## Safety

- gitleaks runs in pre-commit **and** CI; `detect-private-key` + `check-added-large-files` too.
- Secrets: **Secret Manager** for Cloud Run (containers created empty, values added out-of-band);
  a **mounted read-only SA key** for the NAS dashboard (`/secrets/dashboard-sa.json`); **ADC**
  locally (`gcloud auth application-default login`); **WIF** for CI→GCP.
- **Never read, echo, or commit** `.env`, `**/*sa*.json` / service-account keys, `*.tfvars`,
  `*session*`, or `*.tfstate*`. A git-ignored `.env` exists locally — treat as sensitive.

## Environment notes

- The `justfile` runs under **Git Bash** on Windows (`windows-shell` is set to Git Bash, not
  WSL). Chained commands use `&&`.
- Launch Streamlit only via `just dashboard` / `streamlit run` — **never `python app.py`**. The
  dashboard uses a Streamlit v2 component (`st_rsuite`) whose assets are discovered at server
  startup; bare `python` skips that and raises a component-registration error.
