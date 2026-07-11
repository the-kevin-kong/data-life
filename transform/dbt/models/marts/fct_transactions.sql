-- Transaction fact enriched with account + category attributes.
-- Excludes hidden transactions so downstream spend reporting is clean.
with transactions as (
    select * from {{ ref('stg_monarch__transactions') }}
    where not is_hidden
),

accounts as (
    select * from {{ ref('dim_accounts') }}
),

categories as (
    select * from {{ ref('dim_categories') }}
)

select
    transactions.transaction_id,
    transactions.transaction_date,
    transactions.amount,
    -- Monarch stores outflows as negative amounts.
    case
        when transactions.amount < 0 then -transactions.amount
        else 0
    end as spend_amount,
    case
        when transactions.amount > 0 then transactions.amount
        else 0
    end as income_amount,
    transactions.merchant_name,
    transactions.category_id,
    coalesce(categories.category_name, transactions.category_name) as category_name,
    categories.category_group,
    transactions.account_id,
    accounts.account_name,
    accounts.institution_name,
    transactions.is_pending,
    transactions.is_split,
    transactions.needs_review,
    transactions.notes,
    transactions.tags
from transactions
left join accounts on transactions.account_id = accounts.account_id
left join categories on transactions.category_id = categories.category_id
