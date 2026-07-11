with source as (
    select * from {{ source('monarch', 'tags') }}
    where not _is_deleted
)

select
    id as tag_id,
    json_value(data, '$.name') as tag_name,
    json_value(data, '$.color') as tag_color,
    _ingested_at,
    _updated_at
from source
