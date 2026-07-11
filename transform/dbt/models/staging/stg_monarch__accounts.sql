with source as (
    select * from {{ source('monarch', 'accounts') }}
    where not _is_deleted
)

select
    id as account_id,
    json_value(data, '$.displayName') as account_name,
    json_value(data, '$.type.name') as account_type,
    json_value(data, '$.subtype.name') as account_subtype,
    json_value(data, '$.institution.name') as institution_name,
    safe_cast(json_value(data, '$.currentBalance') as float64) as current_balance,
    coalesce(safe_cast(json_value(data, '$.isAsset') as bool), true) as is_asset,
    _ingested_at,
    _updated_at
from source
