# data-life task runner. Install `just` (https://github.com/casey/just), then `just <task>`.
# Every task uses uv so no manual venv activation is needed.

# Run recipes with bash on every OS so the syntax below (&&, inline env vars,
# $VAR) works identically whether you launch `just` from PowerShell or bash.
# On Windows, point explicitly at Git Bash: a bare "bash" resolves to WSL
# (C:\Windows\System32\bash.exe), a separate Linux world with no Windows tools.
set shell := ["bash", "-c"]
set windows-shell := ["C:/Program Files/Git/bin/bash.exe", "-c"]

set dotenv-load := true

# List available tasks.
default:
    @just --list

# Install all workspace deps (single lockfile) + dev tools.
setup:
    uv sync --all-packages
    uvx pre-commit install

# Lint + format check across the workspace.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-fix lint + format.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Static type check.
typecheck:
    uv run mypy packages services apps

# Run the test suite.
test:
    uv run pytest

# Everything CI runs, locally.
check: lint typecheck test

# Run the Monarch -> BigQuery ingestion locally (uses ADC creds).
ingest:
    uv run --package ingest-monarch ingest-monarch

# Run the transaction splitter locally in dry-run mode.
split-dry:
    SPLIT_DRY_RUN=true uv run --package split-transactions split-transactions

# Run the transaction splitter for real (writes back to Monarch).
split:
    SPLIT_DRY_RUN=false uv run --package split-transactions split-transactions

# Build all dbt models + run tests against BigQuery.
dbt-build:
    cd transform/dbt && uv run dbt build

# Parse/compile dbt (no warehouse writes) - used by CI.
dbt-parse:
    cd transform/dbt && uv run dbt parse

# Run the Streamlit dashboard locally.
dashboard:
    uv run --package dashboard streamlit run apps/dashboard/src/dl_dashboard/app.py

# Build the dockerfiles to Artifact Registry
cloud-build:
    gcloud builds submit --config cloudbuild.yaml --substitutions=_REG="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/data-life",_TAG="$(git rev-parse HEAD)" .

# Terraform. Requires terraform installed and GCP_PROJECT_ID set (e.g. in .env).
# The project id is passed via TF_VAR_project_id, never committed.
tf-init:
    cd infra/terraform && terraform init -backend-config="bucket=$GCP_PROJECT_ID-tfstate"

tf-plan:
    cd infra/terraform && TF_VAR_project_id="$GCP_PROJECT_ID" terraform plan

tf-apply:
    cd infra/terraform && TF_VAR_project_id="$GCP_PROJECT_ID" terraform apply
