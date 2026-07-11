import streamlit as st


def menu() -> None:
    st.sidebar.page_link("app.py", label="Financial Overview")
    st.sidebar.page_link("pages/tax_breakdown.py", label="2026 Tax Breakdown")
