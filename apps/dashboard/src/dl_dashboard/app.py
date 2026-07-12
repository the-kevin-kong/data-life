"""data-life dashboard.

Run locally:  uv run --package dashboard streamlit run \
                  apps/dashboard/src/dl_dashboard/app.py
Reads only the BigQuery `marts` dataset via a read-only service account.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import streamlit as st
from st_rsuite.date_range_picker import date_range_picker

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

from dl_dashboard.charts import cashflow_sankey
from dl_dashboard.data import load_activity, load_monthly_spending, load_recent_transactions
from dl_dashboard.menu import menu

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Optional: Make headers pop slightly more with a cleaner weight */
    h1, h2, h3 {
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

menu()

st.set_page_config(page_title="Financial Overview", page_icon="💸", layout="wide")
st.title("💸 Financial Overview")
st.caption("Personal finance analytics — Monarch Money → BigQuery → dbt → Streamlit.")


def _empty_notice() -> None:
    st.info(
        "No data yet. Run the ingestion job and `dbt build`, then refresh. "
        "This dashboard reads the `marts` dataset only."
    )


tab1, tab2 = st.tabs(["😶‍🌫️ At a Glance", "📊 Monthly Spending"])
with tab1:
    try:
        full = load_activity()
    except Exception as exc:
        st.error(f"Could not query BigQuery marts: {exc}")
        st.stop()

    if full.empty:
        _empty_notice()
        st.stop()

    full = full.assign(transaction_date=pd.to_datetime(full["transaction_date"]).dt.date)
    min_date = full["transaction_date"].min()
    max_date = full["transaction_date"].max()
    default_start = max(min_date, max_date - timedelta(days=30))

    # Date control. Filtering runs client-side over the cached last-year+this-year
    # pull, so changing the range never re-queries BigQuery.
    # Anchor shortcuts to the latest transaction date, not today: the picker
    # disables dates past max_date, so ranges ending at `today` would grey out
    # whenever the newest transaction is older than today.
    anchor = max_date
    first_this_month = anchor.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)

    def _clamp(start: date, end: date) -> tuple[date, date]:
        return max(start, min_date), min(end, max_date)

    shortcuts = [
        {"label": "Last 30 days", "value": _clamp(anchor - timedelta(days=30), anchor)},
        {"label": "This month", "value": _clamp(first_this_month, anchor)},
        {"label": "Last month", "value": _clamp(last_month_end.replace(day=1), last_month_end)},
        {"label": "This year", "value": _clamp(date(anchor.year, 1, 1), anchor)},
        {
            "label": "Last year",
            "value": _clamp(date(anchor.year - 1, 1, 1), date(anchor.year - 1, 12, 31)),
        },
    ]

    with st.expander("Date range", expanded=False):
        picked_start, picked_end = date_range_picker(
            label="Report window",
            value=(default_start, max_date),
            min_date=min_date,
            max_date=max_date,
            ranges=shortcuts,
            cleanable=False,
            key="sankey_range",
        )

    start = picked_start or default_start
    end = picked_end or max_date
    activity = full[(full["transaction_date"] >= start) & (full["transaction_date"] <= end)]
    st.caption(f"{start:%b %d, %Y} - {end:%b %d, %Y} · excludes Transfers and pending.")

    if activity.empty:
        st.info("No transactions in the selected range.")
        st.stop()

    # --- KPI row ---------------------------------------------------------------
    total_income = float(activity["income_amount"].sum())
    total_expense = float(activity["spend_amount"].sum())
    savings_rate = (total_income - total_expense) / total_income if total_income > 0 else 0.0
    k1, k2, k3 = st.columns(3)

    def _kpi(col: DeltaGenerator, label: str, value: str, color: str = "inherit") -> None:
        col.markdown(
            f"<div style='font-size:0.8rem;color:#808495'>{label}</div>"
            f"<div style='font-size:1.8rem;font-weight:600;color:{color}'>{value}</div>",
            unsafe_allow_html=True,
        )

    _kpi(k1, "Total income", f"${total_income:,.0f}", "#16a34a")
    _kpi(k2, "Total expense", f"${total_expense:,.0f}", "#dc2626")
    _kpi(k3, "Savings rate", f"{savings_rate:.1%}")

    # --- Cash-flow Sankey ------------------------------------------------------
    sankey = cashflow_sankey(activity)
    if sankey is None:
        st.info("Not enough income and spending in the selected range to chart.")
    else:
        st.plotly_chart(sankey, width="stretch")

    # --- Transactions awaiting review ------------------------------------------
    st.subheader("Awaiting review")
    review = activity[activity["needs_review"]][
        ["transaction_date", "merchant_name", "account_name", "amount"]
    ]
    if review.empty:
        st.success("Nothing awaiting review. 🎉")
    else:
        st.dataframe(review, width="stretch", hide_index=True)


with tab2:
    try:
        monthly = load_monthly_spending()
    except Exception as exc:
        st.error(f"Could not query BigQuery marts: {exc}")
        st.stop()

    if monthly.empty:
        _empty_notice()
        st.stop()

    # --- KPI row ---------------------------------------------------------------
    latest_month = monthly["month"].max()
    this_month = monthly[monthly["month"] == latest_month]
    col1, col2, col3 = st.columns(3)
    col1.metric("Latest month", str(latest_month))
    col2.metric("Spend", f"${this_month['total_spend'].sum():,.0f}")
    col3.metric("Net", f"${this_month['net_amount'].sum():,.0f}")

    # --- Spend over time by category group ------------------------------------
    st.subheader("Monthly spend by category group")
    fig = px.bar(
        monthly,
        x="month",
        y="total_spend",
        color="category_group",
        labels={"total_spend": "Spend ($)", "month": "Month", "category_group": "Category"},
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(legend_title_text="", margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig, width="stretch")

    # --- Recent transactions ---------------------------------------------------
    st.subheader("Recent transactions")
    st.dataframe(load_recent_transactions(), width="stretch", hide_index=True)
