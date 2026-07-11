-- One clean row per (non-deleted) Monarch transaction.
-- JSON paths follow Monarch's transaction shape; adjust here if the API's
-- field names differ after the first live pull.
with source as (
    select * from {{ source('monarch', 'transactions') }}
    where not _is_deleted
)

select
    id as transaction_id,
    safe_cast(json_value(data, '$.date') as date) as transaction_date,
    safe_cast(json_value(data, '$.amount') as float64) as amount,
    json_value(data, '$.merchant.name') as merchant_name,
    json_value(data, '$.category.id') as category_id,
    json_value(data, '$.category.name') as category_name,
    json_value(data, '$.account.id') as account_id,
    json_value(data, '$.notes') as notes,
    array(
        select json_value(tags, '$.name')
        from unnest(json_extract_array(data, '$.tags')) as tags
    ) as tags,
    coalesce(safe_cast(json_value(data, '$.needsReview') as bool), false) as needs_review,
    coalesce(safe_cast(json_value(data, '$.pending') as bool), false) as is_pending,
    coalesce(safe_cast(json_value(data, '$.isSplitTransaction') as bool), false) as is_split,
    coalesce(safe_cast(json_value(data, '$.hideFromReports') as bool), false) as is_hidden,
    _ingested_at,
    _updated_at
from source
