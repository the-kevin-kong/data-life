select
    account_id,
    account_name,
    account_type,
    account_subtype,
    institution_name,
    current_balance,
    is_asset
from {{ ref('stg_monarch__accounts') }}
