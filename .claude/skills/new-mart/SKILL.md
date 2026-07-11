---
name: new-mart
description: Scaffold a new dbt staging or mart model in transform/dbt following the data-life conventions (stg_monarch__/fct_/dim_/mart_ naming, JSON parsing, soft-delete filter, schema tests). Use when adding a dbt model, a new marts table, or surfacing a new Monarch source in the warehouse.
---

# new-mart — scaffold a dbt model

dbt project lives in [transform/dbt](../../../transform/dbt). dbt-core v2 (Fusion), BigQuery
adapter built in. Run everything with `uv run dbt` (or the `just dbt-*` recipes).

## Decide the layer

- **Staging** (`models/staging/stg_monarch__<entity>.sql`) — 1:1 with a raw source, materialized
  as a **view** in the `staging` schema. Cleans/renames only.
- **Mart** (`models/marts/{fct_,dim_,mart_}<name>.sql`) — business model, materialized as a
  **table** in the `marts` schema. `fct_` = facts, `dim_` = dimensions, `mart_` = rollups.

Materialization + schema are set by folder in `dbt_project.yml`; don't override per-model.

## Staging pattern

Raw tables are `{id, data JSON, _ingested_at, _updated_at, _is_deleted, _deleted_at}`. Always
filter soft-deletes and pull fields out of `data` with `json_value`:

```sql
with source as (
    select * from {{ source('monarch', '<table>') }}
    where not _is_deleted
)

select
    id as <entity>_id,
    json_value(data, '$.<field>') as <field>,
    -- json_value(data, '$.nested.field') for nested; json_extract_array(data, '$.items') for arrays
    _ingested_at,
    _updated_at
from source
```

Template: [stg_monarch__categories.sql](../../../transform/dbt/models/staging/stg_monarch__categories.sql).

If the entity is a **new raw source**, first add it under `sources[0].tables` in
[_sources.yml](../../../transform/dbt/models/staging/_sources.yml) — and note that ingestion must
actually land that `monarch.<table>` (see the `dl_ingest` pipeline + `/new-mart`'s upstream:
a `MonarchClient` read + `merge_upsert` call).

## Mart pattern

`ref()` staging models (never `source()` directly from a mart). Monarch stores outflows as
negative amounts — derive `spend_amount`/`income_amount` the way
[fct_transactions.sql](../../../transform/dbt/models/marts/fct_transactions.sql) does; monthly
rollups follow [mart_monthly_spending.sql](../../../transform/dbt/models/marts/mart_monthly_spending.sql).

## Register + test

Add the model to the matching yml with tests
([_staging.yml](../../../transform/dbt/models/staging/_staging.yml) /
[_marts.yml](../../../transform/dbt/models/marts/_marts.yml)):

```yaml
  - name: <model_name>
    description: <one line>
    columns:
      - name: <pk>_id
        data_tests: [not_null, unique]
      - name: <fk>_id
        data_tests:
          - relationships:
              arguments:
                to: ref('<dim_model>')
                field: <fk>_id
```

## Verify

1. Offline (no BigQuery, same as CI): `just dbt-parse`.
2. With ADC + `GCP_PROJECT_ID` set: `just dbt-build` (builds + runs tests). To iterate on one
   model: `cd transform/dbt && uv run dbt build --select <model_name>+`.

The dashboard reads `marts` only — if the model should surface there, add a cached query in
[apps/dashboard/src/dl_dashboard/data.py](../../../apps/dashboard/src/dl_dashboard/data.py).
