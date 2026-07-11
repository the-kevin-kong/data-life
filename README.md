# data-life

[![CI](https://github.com/the-kevin-kong/data-life/actions/workflows/ci.yml/badge.svg)](https://github.com/the-kevin-kong/data-life/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

<!-- Update the repo slug above if the GitHub path differs. -->

A personal data platform monorepo. It ingests financial data from
[Monarch Money](https://www.monarchmoney.com/), lands it in **BigQuery**,
models it with **dbt**, and serves reports through a self-hosted **Streamlit**
dashboard. It also automatically **splits tagged transactions** back into
Monarch on a schedule.

> **Public code, private data.** This repository is a portfolio showcase. All
> data lives in a private BigQuery project and every credential lives in Google
> Secret Manager — nothing sensitive is ever committed. See
> [Security](#security).

---

## Architecture

```
Cloud Scheduler (cron)
   │  daily
   ├─► Cloud Run: ingest-monarch ──► BigQuery  raw.*   (MERGE-upsert + soft-delete)
   │                                     │
   ├─► Cloud Run: dbt build       ──► BigQuery  staging.* → marts.*  (+ tests, docs)
   │
   └─► Cloud Run: split-transactions ─► Monarch API  (read tagged txns → write splits → re-tag)

Secret Manager ── monarch creds · MFA (TOTP) seed · persisted session blob
Streamlit (NAS, Docker) ──read-only SA──► BigQuery marts.*   ──► SWAG + Cloudflare ──► web
```

Data flow is **ELT**: land the full current state in `raw` via MERGE-upsert
(one row per record, deletions captured as soft-deletes), then let dbt own all
typing and modeling in `staging` → `marts`. The dashboard only reads `marts`.

See [docs/architecture.md](docs/architecture.md) for the full design.

## Repository layout

| Path | What it is |
| --- | --- |
| [packages/common](packages/common) | `dl_common`: settings, logging, BigQuery MERGE-upsert loader, Secret Manager access |
| [packages/monarch-client](packages/monarch-client) | `dl_monarch`: wrapper over the Monarch fork (automated auth + session, typed reads) |
| [services/ingest-monarch](services/ingest-monarch) | Cloud Run: pull Monarch → `raw.*` |
| [services/split-transactions](services/split-transactions) | Cloud Run: tag-driven transaction splitter |
| [transform/dbt](transform/dbt) | dbt-bigquery project (`staging` → `marts`) |
| [apps/dashboard](apps/dashboard) | Streamlit dashboard (Docker, deploys to NAS) |
| [infra/terraform](infra/terraform) | All GCP infrastructure as code |

## Tech stack

- **GCP** project set via `GCP_PROJECT_ID` (`us-central1`)
- **uv** workspace (single lockfile, per-package deps), Python 3.12
- **Cloud Run** + **Cloud Scheduler** (serverless, near-free at personal scale)
- **BigQuery** warehouse, **dbt Core v2.0 (Fusion)** transforms
- **Terraform** IaC, **GitHub Actions** CI (keyless deploy via Workload Identity Federation)
- **Streamlit** dashboard, self-hosted on a NAS behind SWAG + Cloudflare

> ℹ️ dbt Core v2.0 (Fusion) is a preview/RC release; pinned intentionally as a
> forward-looking choice. The BigQuery adapter is built into Fusion.

## Quickstart (local dev)

```bash
# Prereqs: uv, gcloud (authenticated), Python 3.12 (uv will fetch it)
gcloud auth application-default login   # local ADC credentials
cp .env.example .env                    # adjust if needed (no secrets go here)

uv sync --all-packages                  # install everything
uv run pytest                           # run tests
just ingest                             # pull Monarch -> BigQuery raw.*
just dbt-build                          # build + test dbt models
just dashboard                          # launch Streamlit locally
just split-dry                          # preview transaction splits (no writes)
```

(`just` is optional — every task maps to a `uv run …` command.)

## Security

- Secrets never touch git: `.gitignore` blocks `.env`, keys, tfvars, and session
  blobs; a **gitleaks** pre-commit hook is a backstop.
- Terraform creates Secret Manager secrets **empty**; values are added
  out-of-band via `gcloud`.
- Cloud Run services run as least-privilege service accounts. CI deploys to GCP
  with **Workload Identity Federation** (no long-lived keys). The dashboard uses
  a **read-only** BigQuery service account.

## License

[MIT](LICENSE)
