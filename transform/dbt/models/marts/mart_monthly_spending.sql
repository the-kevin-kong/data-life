-- Monthly spend by category group; the dashboard's primary summary source.
select
    date_trunc(transaction_date, month) as month,
    category_group,
    count(*) as txn_count,
    sum(spend_amount) as total_spend,
    sum(income_amount) as total_income,
    sum(income_amount) - sum(spend_amount) as net_amount
from {{ ref('fct_transactions') }}
where not is_pending
group by 1, 2
