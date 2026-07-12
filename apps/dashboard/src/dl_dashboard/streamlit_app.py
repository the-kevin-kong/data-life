"""data-life dashboard entry point.

Run locally:  uv run --package dashboard streamlit run \
                  apps/dashboard/src/dl_dashboard/streamlit_app.py
Reads only the BigQuery `marts` dataset via a read-only service account.

`st.set_page_config` must be the first Streamlit call, so it lives here, before
`st.navigation` builds the sidebar and dispatches to the selected page.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="data-life", page_icon=":material/savings:", layout="wide")

page = st.navigation(
    [
        st.Page(
            "app_pages/overview.py",
            title="Financial overview",
            icon=":material/account_balance_wallet:",
            default=True,
        ),
        st.Page(
            "app_pages/tax_breakdown.py",
            title="2026 tax breakdown",
            icon=":material/receipt_long:",
        ),
    ]
)
page.run()
