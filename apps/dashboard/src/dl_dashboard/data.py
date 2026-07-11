"""Cached BigQuery access for the dashboard (read-only marts)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dl_common import BigQueryClient


@st.cache_resource
def _client() -> BigQueryClient:
    return BigQueryClient()


@st.cache_data(ttl=3600)
def load_monthly_spending() -> pd.DataFrame:
    sql = "select * from marts.mart_monthly_spending order by month"
    return _client().query(sql).to_dataframe()


@st.cache_data(ttl=3600)
def load_activity() -> pd.DataFrame:
    """Transactions from Jan 1 of last year through today, excluding pending and
    Transfers.

    The full previous-year + current-year window is fetched once and cached so
    the dashboard can filter to any sub-range client-side without re-querying.
    Money-movement rows (the Transfers category group) are dropped so income and
    spend reflect real cash flow, not internal moves.
    """
    sql = """
        select
            transaction_date,
            merchant_name,
            account_name,
            amount,
            income_amount,
            spend_amount,
            category_name,
            category_group,
            needs_review
        from marts.fct_transactions
        where transaction_date >= date_sub(date_trunc(current_date(), year), interval 1 year)
          and not is_pending
          and coalesce(lower(category_group), '') != 'transfers'
          and coalesce(lower(category_name), '') != 'transfers'
        order by transaction_date desc
    """
    return _client().query(sql).to_dataframe()


@st.cache_data(ttl=3600)
def load_recent_transactions(limit: int = 200, filter: str = "1=1") -> pd.DataFrame:
    sql = f"""
        select *
        from marts.fct_transactions
        where {filter}
        order by transaction_date desc
        limit {int(limit)}
    """
    return _client().query(sql).to_dataframe()
