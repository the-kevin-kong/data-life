with source as (
    select * from {{ source('monarch', 'categories') }}
    where not _is_deleted
)

select
    id as category_id,
    json_value(data, '$.name') as category_name,
    json_value(data, '$.group.name') as category_group,
    json_value(data, '$.group.type') as category_type,
    _ingested_at,
    _updated_at
from source
