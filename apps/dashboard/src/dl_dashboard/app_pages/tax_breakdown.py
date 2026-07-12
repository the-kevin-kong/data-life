"""2026 tax breakdown — actuals (YTD from the ledger) vs year-end estimation."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dl_dashboard.data import load_recent_transactions
from pandas.io.formats.style import Styler

st.title("2026 tax breakdown")

# -----------------------------------------------------------------------------
# 1. PLACEHOLDER DATA SOURCE (Comprehensive Ledger)
# -----------------------------------------------------------------------------
ledger_df = load_recent_transactions(
    limit=500,
    filter="""
        regexp_contains(array_to_string(tags, ','), '(Business|Bombas|Tax|Deduction)')
        and extract(year from transaction_date) = 2026
        """,
)


# -----------------------------------------------------------------------------
# 2. DYNAMIC TAX FORMULA ENGINE (Exact logic from spreadsheet)
# -----------------------------------------------------------------------------
def calc_se_tax(net_earnings: float, w2_income: float) -> float:
    cap = 184500  # Spreadsheet cap limit
    if w2_income >= cap:
        return net_earnings * 0.029
    else:
        rem_cap = max(0, cap - w2_income)
        ss_earnings = min(net_earnings, rem_cap)
        return ss_earnings * 0.124 + net_earnings * 0.029


def calc_fed_tax(taxable_income: float) -> float:
    if taxable_income <= 24800:
        return taxable_income * 0.10
    elif taxable_income <= 100800:
        return 2480 + 0.12 * (taxable_income - 24800)
    elif taxable_income <= 211400:
        return 11600 + 0.22 * (taxable_income - 100800)
    elif taxable_income <= 403550:
        return 35932 + 0.24 * (taxable_income - 211400)
    else:
        return 82048 + 0.32 * (taxable_income - 403550)


def calc_ny_tax(w2_income: float, contrib_529: float) -> float:
    base = w2_income - contrib_529
    if base <= 27900:
        return base * 0.04
    elif base <= 161550:
        return 1116 + 0.0475 * (base - 27900)
    elif base <= 323200:
        return 7465 + 0.0525 * (base - 161550)
    else:
        return 15951 + 0.0585 * (base - 323200)


def calc_nj_tax(agi: float) -> float:
    if agi <= 20000:
        return agi * 0.014
    elif agi <= 50000:
        return 280 + 0.0175 * (agi - 20000)
    elif agi <= 70000:
        return 805 + 0.0245 * (agi - 50000)
    elif agi <= 80000:
        return 1295.5 + 0.035 * (agi - 70000)
    elif agi <= 150000:
        return 1645 + 0.05525 * (agi - 80000)
    elif agi <= 500000:
        return 5512.5 + 0.0637 * (agi - 150000)
    else:
        return 27807.5 + 0.0897 * (agi - 500000)


def calc_nj_credit(ny_tax: float, nj_tax: float, w2_income: float, agi: float) -> float:
    if agi == 0:
        return 0.0
    return min(ny_tax, nj_tax * (w2_income / agi))


# -----------------------------------------------------------------------------
# 3. SIDEBAR USER INPUTS (Yellow Highlighted Cells Replacement)
# -----------------------------------------------------------------------------
st.sidebar.header("Interactive inputs (YE estimation)")

with st.sidebar.expander("Income projections", expanded=True, icon=":material/trending_up:"):
    ye_w2_gross = st.number_input("Bombas W-2 gross income", value=194644.0, step=1000.0)
    ye_ira_withdrawal = st.number_input(
        "Inherited IRA gross withdrawal", value=35000.0, step=1000.0
    )
    ye_sched_c_inc = st.number_input("Schedule C income", value=65000.0, step=1000.0)
    ye_sched_c_exp = st.number_input("Schedule C expense", value=-61.25, step=5.0)
    ye_home_office = st.number_input("Home office expense", value=-880.0, step=5.0)

with st.sidebar.expander("Solo 401k & deductions", expanded=False, icon=":material/shield:"):
    ye_shared_deferrals = st.number_input(
        "Shared 401k deferrals at Bombas", value=24500.0, step=500.0
    )
    ye_after_tax_cash = st.number_input("Actual after-tax cash contributed", value=0.0, step=500.0)
    ye_401k_contribs = st.number_input("401k contributions deduction", value=24500.0, step=500.0)
    ye_hsa_contribs = st.number_input("HSA contributions deduction", value=8500.0, step=500.0)
    ye_employer_401k = st.number_input("Solo 401k employer contributions", value=0.0, step=500.0)
    ye_529_contribs = st.number_input("529 contributions", value=10000.0, step=500.0)

with st.sidebar.expander(
    "Taxes paid & withholdings", expanded=False, icon=":material/account_balance:"
):
    ye_fed_withheld_w2 = st.number_input("Federal tax withheld (W-2)", value=-10287.70, step=500.0)
    ye_fed_withheld_ira = st.number_input("Federal tax withheld (IRA)", value=-13939.10, step=500.0)
    ye_fed_estimated = st.number_input(
        "Federal quarterly estimated paid", value=-39728.00, step=500.0
    )
    ye_ny_estimated = st.number_input("NY quarterly estimated paid", value=-8298.00, step=500.0)
    ye_ny_withheld_w2 = st.number_input("NY tax withheld (W-2)", value=0.0, step=500.0)
    ye_nj_withheld_w2 = st.number_input("NJ tax withheld (W-2)", value=-5979.55, step=500.0)
    ye_nj_estimated = st.number_input("NJ quarterly estimated paid", value=0.0, step=500.0)

# -----------------------------------------------------------------------------
# 4. COMPUTE ACTUALS (YTD) USING EXACT SPREADSHEET SUMIFS FILTERS
# -----------------------------------------------------------------------------
# Income Inputs
act_w2_gross = ledger_df.loc[ledger_df["category_name"] == "Bombas Gross Pay", "amount"].sum()
act_ira_withdrawal = 0.0
act_sched_c_inc = ledger_df.loc[
    (ledger_df["tags"].astype(str).str.contains("Business")) & (ledger_df["amount"] > 0), "amount"
].sum()
act_sched_c_exp = ledger_df.loc[
    (ledger_df["tags"].astype(str).str.contains("Business")) & (ledger_df["amount"] < 0), "amount"
].sum()
act_home_office = -880.0

# Solo 401k Tracker
act_shared_deferrals = 24500.0
act_after_tax_cash = 0.0

# Federal Taxes Paid
act_fed_withheld_w2 = ledger_df.loc[
    (ledger_df["category_name"] == "Federal Taxes") & (ledger_df["merchant_name"] == "Bombas"),
    "amount",
].sum()
act_fed_withheld_ira = 0.0
act_fed_estimated = ledger_df.loc[
    (ledger_df["category_name"] == "Federal Taxes")
    & (ledger_df["merchant_name"] != "Bombas")
    & (~ledger_df["tags"].astype(str).str.contains("Previous Tax Year", na=False, case=False)),
    "amount",
].sum()

# NY State Taxes Paid
act_ny_withheld_w2 = ledger_df.loc[
    (ledger_df["category_name"] == "NY State Taxes") & (ledger_df["merchant_name"] == "Bombas"),
    "amount",
].sum()
act_ny_estimated = ledger_df.loc[
    (ledger_df["category_name"] == "NY State Taxes")
    & (ledger_df["merchant_name"] != "Bombas")
    & (~ledger_df["tags"].astype(str).str.contains("Previous Tax Year", na=False, case=False)),
    "amount",
].sum()

# NJ State Taxes Paid
act_nj_withheld_w2 = ledger_df.loc[
    (ledger_df["category_name"] == "NJ State Taxes") & (ledger_df["merchant_name"] == "Bombas"),
    "amount",
].sum()
act_nj_estimated = ledger_df.loc[
    (ledger_df["category_name"] == "NJ State Taxes")
    & (ledger_df["merchant_name"] != "Bombas")
    & (~ledger_df["tags"].astype(str).str.contains("Previous Tax Year", na=False, case=False)),
    "amount",
].sum()

# Deductions (Spreadsheet uses -SUMIF, so we negate)
act_401k_contribs = -ledger_df.loc[
    ledger_df["category_name"] == "401K Contribution", "amount"
].sum()
act_hsa_contribs = -ledger_df.loc[ledger_df["category_name"] == "HSA Contribution", "amount"].sum()
act_employer_401k = -ledger_df.loc[ledger_df["merchant_name"] == "Charles Schwab", "amount"].sum()
act_529_contribs = -ledger_df.loc[ledger_df["category_name"] == "Education", "amount"].sum()

# -----------------------------------------------------------------------------
# 5. DYNAMIC FORMULA CALCULATIONS
# -----------------------------------------------------------------------------
# Actuals
act_net_sched_c = act_sched_c_inc + act_sched_c_exp + act_home_office
act_household_gross = act_w2_gross + act_ira_withdrawal + act_net_sched_c
act_net_earned_401k = act_net_sched_c - (calc_se_tax(act_net_sched_c * 0.9235, act_w2_gross) / 2)
act_max_employer_cap = act_net_earned_401k * 0.20
act_rem_employer = act_max_employer_cap - act_employer_401k
act_max_mega_cap = min(act_net_earned_401k, 72000.0)
act_rem_mega = act_max_mega_cap - act_shared_deferrals - act_max_employer_cap - act_after_tax_cash

# YE Estimation
ye_net_sched_c = ye_sched_c_inc + ye_sched_c_exp + ye_home_office
ye_household_gross = ye_w2_gross + ye_ira_withdrawal + ye_net_sched_c
ye_net_earned_401k = ye_net_sched_c - (calc_se_tax(ye_net_sched_c * 0.9235, ye_w2_gross) / 2)
ye_max_employer_cap = ye_net_earned_401k * 0.20
ye_rem_employer = ye_max_employer_cap - ye_employer_401k
ye_max_mega_cap = min(ye_net_earned_401k, 72000.0)
ye_rem_mega = ye_max_mega_cap - ye_shared_deferrals - ye_max_employer_cap - ye_after_tax_cash

# Taxes Paid Log
act_total_fed_paid = act_fed_withheld_w2 + act_fed_withheld_ira + act_fed_estimated
ye_total_fed_paid = ye_fed_withheld_w2 + ye_fed_withheld_ira + ye_fed_estimated

act_total_ny_paid = act_ny_withheld_w2 + act_ny_estimated
ye_total_ny_paid = ye_ny_withheld_w2 + ye_ny_estimated

act_total_nj_paid = act_nj_withheld_w2 + act_nj_estimated
ye_total_nj_paid = ye_nj_withheld_w2 + ye_nj_estimated

# Final Tax Calculator
se_modifier = 0.9235
act_se_subject = act_net_sched_c * se_modifier
ye_se_subject = ye_net_sched_c * se_modifier

act_se_tax_val = calc_se_tax(act_se_subject, act_w2_gross)
ye_se_tax_val = calc_se_tax(ye_se_subject, ye_w2_gross)

act_half_se = act_se_tax_val / 2
ye_half_se = ye_se_tax_val / 2

act_agi = (
    act_household_gross - act_half_se - act_401k_contribs - act_hsa_contribs - act_employer_401k
)
ye_agi = ye_household_gross - ye_half_se - ye_401k_contribs - ye_hsa_contribs - ye_employer_401k

std_deduction = 32200.0
act_taxable_inc = max(0.0, act_agi - std_deduction)
ye_taxable_inc = max(0.0, ye_agi - std_deduction)

act_fed_tax_val = calc_fed_tax(act_taxable_inc)
ye_fed_tax_val = calc_fed_tax(ye_taxable_inc)

act_fed_bal = act_fed_tax_val + act_se_tax_val + act_total_fed_paid
ye_fed_bal = ye_fed_tax_val + ye_se_tax_val + ye_total_fed_paid

act_ny_tax_val = calc_ny_tax(act_w2_gross, act_529_contribs)
ye_ny_tax_val = calc_ny_tax(ye_w2_gross, ye_529_contribs)
act_ny_bal = act_ny_tax_val + act_total_ny_paid
ye_ny_bal = ye_ny_tax_val + ye_total_ny_paid

act_nj_gross_tax = calc_nj_tax(act_agi)
ye_nj_gross_tax = calc_nj_tax(ye_agi)

act_nj_credit = calc_nj_credit(act_ny_tax_val, act_nj_gross_tax, act_w2_gross, act_agi)
ye_nj_credit = calc_nj_credit(ye_ny_tax_val, ye_nj_gross_tax, ye_w2_gross, ye_agi)

act_nj_net = act_nj_gross_tax - act_nj_credit
ye_nj_net = ye_nj_gross_tax - ye_nj_credit

act_nj_bal = act_nj_net + act_total_nj_paid
ye_nj_bal = ye_nj_net + ye_total_nj_paid

# -----------------------------------------------------------------------------
# 6. APP RENDER LAYOUT
# -----------------------------------------------------------------------------
# Subtotal rows are bolded; ratio rows format as a plain 4-dp number, everything
# else as currency. Membership is keyed by the row label.
Row = tuple[str, float, float]

BOLD_LABELS = {
    "Net Schedule C profit",
    "Total household gross income",
    "Remaining employer contribution capacity",
    "Remaining mega backdoor capacity",
    "Total federal taxes paid so far",
    "Total NY state taxes paid so far",
    "Total NJ state taxes paid so far",
    "Adjusted gross income (AGI)",
    "Total estimated federal taxable income",
    "Total federal balance due / (refund)",
    "Total NY state balance due / (refund)",
    "Total NJ state balance due / (refund)",
}
RATIO_LABELS = {"Schedule C SE tax modifier"}

income_rows: list[Row] = [
    ("Bombas W-2 gross income", act_w2_gross, ye_w2_gross),
    ("Inherited IRA gross withdrawal", act_ira_withdrawal, ye_ira_withdrawal),
    ("Schedule C income", act_sched_c_inc, ye_sched_c_inc),
    ("Schedule C expense", act_sched_c_exp, ye_sched_c_exp),
    ("Home office expense", act_home_office, ye_home_office),
    ("Net Schedule C profit", act_net_sched_c, ye_net_sched_c),
    ("Total household gross income", act_household_gross, ye_household_gross),
]

solo_401k_rows: list[Row] = [
    ("Shared 401k deferrals made at Bombas", act_shared_deferrals, ye_shared_deferrals),
    ("2026 IRS maximum total addition limit", 72000.0, 72000.0),
    ("Net earned income for Solo 401k", act_net_earned_401k, ye_net_earned_401k),
    ("Maximum employer contribution capacity", act_max_employer_cap, ye_max_employer_cap),
    ("Employer contributed", act_employer_401k, ye_employer_401k),
    ("Remaining employer contribution capacity", act_rem_employer, ye_rem_employer),
    ("Maximum mega backdoor capacity", act_max_mega_cap, ye_max_mega_cap),
    ("After-tax cash contributed", act_after_tax_cash, ye_after_tax_cash),
    ("Remaining mega backdoor capacity", act_rem_mega, ye_rem_mega),
]

taxes_paid_rows: list[Row] = [
    ("Federal tax withheld from Bombas W-2", act_fed_withheld_w2, ye_fed_withheld_w2),
    ("Federal tax withheld from inherited IRA", act_fed_withheld_ira, ye_fed_withheld_ira),
    ("Federal quarterly estimated payments paid", act_fed_estimated, ye_fed_estimated),
    ("Total federal taxes paid so far", act_total_fed_paid, ye_total_fed_paid),
    ("NY tax withheld from Bombas W-2", act_ny_withheld_w2, ye_ny_withheld_w2),
    ("NY quarterly estimated payments paid", act_ny_estimated, ye_ny_estimated),
    ("Total NY state taxes paid so far", act_total_ny_paid, ye_total_ny_paid),
    ("NJ tax withheld from Bombas W-2", act_nj_withheld_w2, ye_nj_withheld_w2),
    ("NJ tax estimated payments paid", act_nj_estimated, ye_nj_estimated),
    ("Total NJ state taxes paid so far", act_total_nj_paid, ye_total_nj_paid),
]

final_calc_rows: list[Row] = [
    ("Schedule C SE tax modifier", se_modifier, se_modifier),
    ("Net earnings subject to SE tax", act_se_subject, ye_se_subject),
    ("Calculated self-employment tax", act_se_tax_val, ye_se_tax_val),
    ("Half of SE tax deduction", act_half_se, ye_half_se),
    ("401k contributions", act_401k_contribs, ye_401k_contribs),
    ("HSA contributions", act_hsa_contribs, ye_hsa_contribs),
    ("Adjusted gross income (AGI)", act_agi, ye_agi),
    ("2026 standard deduction (MFJ)", std_deduction, std_deduction),
    ("Total estimated federal taxable income", act_taxable_inc, ye_taxable_inc),
    ("Calculated federal income tax", act_fed_tax_val, ye_fed_tax_val),
    ("Total federal balance due / (refund)", act_fed_bal, ye_fed_bal),
]

new_york_rows: list[Row] = [
    ("NY AGI", act_w2_gross, ye_w2_gross),
    ("529 contribution", act_529_contribs, ye_529_contribs),
    ("Calculated NY state income tax", act_ny_tax_val, ye_ny_tax_val),
    ("Total NY state balance due / (refund)", act_ny_bal, ye_ny_bal),
]

new_jersey_rows: list[Row] = [
    ("Calculated gross NJ state income tax", act_nj_gross_tax, ye_nj_gross_tax),
    ("Calculated NJ credit for NY taxes paid", act_nj_credit, ye_nj_credit),
    ("Net NJ state tax liability", act_nj_net, ye_nj_net),
    ("Total NJ state balance due / (refund)", act_nj_bal, ye_nj_bal),
]


def _fmt(label: str, value: float) -> str:
    """Ratio rows as a 4-dp number, everything else as currency."""
    return f"{value:.4f}" if label in RATIO_LABELS else f"${value:,.2f}"


# Subtotal rows: bold + the theme's secondary background (matches the Sankey panel).
_SUBTOTAL_STYLE = "font-weight: bold; background-color: #232731"


def _bold_subtotals(row: pd.Series) -> list[str]:
    # Key on the label column. The label is a real column (not the index) because
    # st.dataframe renders a Styler's body-cell styles only, not index/header styles.
    style = _SUBTOTAL_STYLE if row["Line item"] in BOLD_LABELS else ""
    return [style] * len(row)


def _section(rows: list[Row]) -> Styler:
    """Build a styled Line item / Actual / Year-end table.

    Values are pre-formatted per row (currency vs ratio); subtotal rows — label
    cell included — are bolded and shaded.
    """
    frame = pd.DataFrame(
        {
            "Line item": [label for label, _, _ in rows],
            "Actual": [_fmt(label, act) for label, act, _ in rows],
            "Year-end": [_fmt(label, ye) for label, _, ye in rows],
        }
    )
    return frame.style.apply(_bold_subtotals, axis=1)


def _show_section(title: str, rows: list[Row]) -> None:
    """Render a section, sized to show every row without an inner scrollbar."""
    st.subheader(title)
    # ~35px per row + header; a small buffer avoids a stray scrollbar.
    st.dataframe(
        _section(rows),
        width="stretch",
        hide_index=True,
        height=35 * (len(rows) + 1) + 5,
    )


tab1, tab2 = st.tabs(["Tax & contribution calculator", "Ledger (data source)"])

with tab1:
    _show_section("Income inputs", income_rows)
    _show_section("Solo 401k tracker", solo_401k_rows)
    _show_section("Taxes paid log (withholdings & estimated payments)", taxes_paid_rows)
    _show_section("Final tax calculator & liability balance", final_calc_rows)
    _show_section("New York", new_york_rows)
    _show_section("New Jersey", new_jersey_rows)

with tab2:
    st.subheader("Underlying transactions ledger")
    st.dataframe(
        ledger_df,
        width="stretch",
        hide_index=True,
        column_config={"amount": st.column_config.NumberColumn("Amount", format="$%.2f")},
    )
