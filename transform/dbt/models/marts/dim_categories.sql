select
    category_id,
    category_name,
    category_group,
    category_type
from {{ ref('stg_monarch__categories') }}
