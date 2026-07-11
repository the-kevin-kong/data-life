# Cloud Run Job that runs `dbt build` against BigQuery.
# Build context is the repo root:
#   docker build -f transform/dbt/Dockerfile -t dbt-build .
FROM python:3.12-slim

WORKDIR /dbt
# dbt Core v2.0 via the Fusion distribution (BigQuery adapter is built in).
RUN pip install --no-cache-dir --pre "dbt>=2.0.0rc196"

COPY transform/dbt /dbt
ENV DBT_PROFILES_DIR=/dbt

# Vendor dbt packages (dbt_utils) at build time.
RUN dbt deps

# Auth is via ADC (the job's runtime service account). Datasets/project come
# from env vars set on the Cloud Run Job.
CMD ["dbt", "build"]
