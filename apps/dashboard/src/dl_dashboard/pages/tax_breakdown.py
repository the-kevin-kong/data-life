import streamlit as st
from dl_dashboard.data import load_recent_transactions
from dl_dashboard.menu import menu

menu()

# Set page configuration
st.set_page_config(
    page_title="2026 Tax Breakdown",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean spreadsheet-like styling
st.markdown(
    """
    <style>
    .reportview-container { background: #f5f7f9; }
    .main-header { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; }
    .section-header {
        font-size: 18px; font-weight: bold; color: #2563EB;
        background-color: #EFF6FF; padding: 8px; border-left: 5px solid #2563EB;
        margin-top: 20px; margin-bottom: 10px;
    }
    .total-row { font-weight: bold; background-color: #F3F4F6; }
    </style>
""",
    unsafe_allow_html=True,
)


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
def calc_se_tax(net_earnings, w2_income):
    cap = 184500  # Spreadsheet cap limit
    if w2_income >= cap:
        return net_earnings * 0.029
    else:
        rem_cap = max(0, cap - w2_income)
        ss_earnings = min(net_earnings, rem_cap)
        return ss_earnings * 0.124 + net_earnings * 0.029


def calc_fed_tax(taxable_income):
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


def calc_ny_tax(w2_income, contrib_529):
    base = w2_income - contrib_529
    if base <= 27900:
        return base * 0.04
    elif base <= 161550:
        return 1116 + 0.0475 * (base - 27900)
    elif base <= 323200:
        return 7465 + 0.0525 * (base - 161550)
    else:
        return 15951 + 0.0585 * (base - 323200)


def calc_nj_tax(agi):
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


def calc_nj_credit(ny_tax, nj_tax, w2_income, agi):
    if agi == 0:
        return 0
    return min(ny_tax, nj_tax * (w2_income / agi))


# -----------------------------------------------------------------------------
# 3. SIDEBAR USER INPUTS (Yellow Highlighted Cells Replacement)
# -----------------------------------------------------------------------------
st.sidebar.header("🔧 Interactive Inputs (YE Estimation)")

with st.sidebar.expander("📈 Income Projections", expanded=True):
    ye_w2_gross = st.number_input("Bombas W-2 Gross Income", value=194644.0, step=1000.0)
    ye_ira_withdrawal = st.number_input(
        "Inherited IRA Gross Withdrawal", value=35000.0, step=1000.0
    )
    ye_sched_c_inc = st.number_input("Schedule C Income", value=65000.0, step=1000.0)
    ye_sched_c_exp = st.number_input("Schedule C Expense", value=-61.25, step=5.0)
    ye_home_office = st.number_input("Home Office Expense", value=-880.0, step=5.0)

with st.sidebar.expander("🛡️ Solo 401k & Deductions", expanded=False):
    ye_shared_deferrals = st.number_input(
        "Shared 401k Deferrals at Bombas", value=24500.0, step=500.0
    )
    ye_after_tax_cash = st.number_input("Actual After-Tax Cash Contributed", value=0.0, step=500.0)
    ye_401k_contribs = st.number_input("401k Contributions Deduction", value=24500.0, step=500.0)
    ye_hsa_contribs = st.number_input("HSA Contributions Deduction", value=8500.0, step=500.0)
    ye_employer_401k = st.number_input("Solo 401k Employer Contributions", value=0.0, step=500.0)
    ye_529_contribs = st.number_input("529 Contributions", value=10000.0, step=500.0)

with st.sidebar.expander("🏛️ Taxes Paid & Withholdings", expanded=False):
    ye_fed_withheld_w2 = st.number_input("Federal Tax Withheld (W-2)", value=-10287.70, step=500.0)
    ye_fed_withheld_ira = st.number_input("Federal Tax Withheld (IRA)", value=-13939.10, step=500.0)
    ye_fed_estimated = st.number_input(
        "Federal Quarterly Estimated Paid", value=-39728.00, step=500.0
    )
    ye_ny_estimated = st.number_input("NY Quarterly Estimated Paid", value=-8298.00, step=500.0)
    ye_ny_withheld_w2 = st.number_input("NY Tax Withheld (W-2)", value=0.0, step=500.0)
    ye_nj_withheld_w2 = st.number_input("NJ Tax Withheld (W-2)", value=-5979.55, step=500.0)
    ye_nj_estimated = st.number_input("NJ Quarterly Estimated Paid", value=0.0, step=500.0)

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
st.title("💼 2026 Tax Breakdown")

tab1, tab2 = st.tabs(["📊 Tax & Contribution Calculator", "📋 Ledger (Data Source)"])

with tab1:
    st.markdown(
        '<div class="main-header">2026 Tax & Contribution Calculator</div>', unsafe_allow_html=True
    )

    def render_row(label, val1, val2, is_header=False, is_bold=False, is_currency=True):
        if is_header:
            st.markdown(f'<div class="section-header">{label}</div>', unsafe_allow_html=True)
        else:
            c1, c2, c3 = st.columns([4, 2, 2])
            weight = "bold" if is_bold else "normal"
            c1.markdown(
                f"<span style='font-weight:{weight};'>{label}</span>", unsafe_allow_html=True
            )
            c2.markdown(
                f"<span style='font-weight:{weight};'>${val1:,.2f}</span>"
                if is_currency and isinstance(val1, int | float)
                else f"<span>{val1}</span>",
                unsafe_allow_html=True,
            )
            c3.markdown(
                f"<span style='font-weight:{weight};'>${val2:,.2f}</span>"
                if is_currency and isinstance(val2, int | float)
                else f"<span>{val2}</span>",
                unsafe_allow_html=True,
            )

    render_row("INCOME INPUTS", "", "", is_header=True)
    render_row("Bombas W-2 Gross Income", act_w2_gross, ye_w2_gross)
    render_row("Inherited IRA Gross Withdrawal", act_ira_withdrawal, ye_ira_withdrawal)
    render_row("Schedule C Income", act_sched_c_inc, ye_sched_c_inc)
    render_row("Schedule C Expense", act_sched_c_exp, ye_sched_c_exp)
    render_row("Home Office Expense", act_home_office, ye_home_office)
    render_row("Net Schedule C Profit", act_net_sched_c, ye_net_sched_c, is_bold=True)
    render_row(
        "Total Household Gross Income", act_household_gross, ye_household_gross, is_bold=True
    )

    render_row("SOLO 401K TRACKER", "", "", is_header=True)
    render_row("Shared 401k Deferrals Made at Bombas", act_shared_deferrals, ye_shared_deferrals)
    render_row("2026 IRS Maximum Total Addition Limit", 72000.0, 72000.0)
    render_row("Net Earned Income for Solo 401k", act_net_earned_401k, ye_net_earned_401k)
    render_row("Maximum Employer Contribution Capacity", act_max_employer_cap, ye_max_employer_cap)
    render_row("Employer Contributed", act_employer_401k, ye_employer_401k)
    render_row(
        "Remaining Employer Contribution Capacity", act_rem_employer, ye_rem_employer, is_bold=True
    )
    render_row("Maximum Mega Backdoor Capacity", act_max_mega_cap, ye_max_mega_cap)
    render_row("After-Tax Cash Contributed", act_after_tax_cash, ye_after_tax_cash)
    render_row("Remaining Mega BackdoorCapacity", act_rem_mega, ye_rem_mega, is_bold=True)

    render_row("TAXES PAID LOG (Withholdings & Estimated Payments)", "", "", is_header=True)
    render_row("Federal Tax Withheld from Bombas W-2", act_fed_withheld_w2, ye_fed_withheld_w2)
    render_row("Federal Tax Withheld from Inherited IRA", act_fed_withheld_ira, ye_fed_withheld_ira)
    render_row("Federal Quarterly Estimated Payments Paid", act_fed_estimated, ye_fed_estimated)
    render_row(
        "Total Federal Taxes Paid So Far", act_total_fed_paid, ye_total_fed_paid, is_bold=True
    )
    render_row("NY Tax Withheld from Bombas W-2", act_ny_withheld_w2, ye_ny_withheld_w2)
    render_row("NY Quarterly Estimated Payments Paid", act_ny_estimated, ye_ny_estimated)
    render_row(
        "Total NY State Taxes Paid So Far", act_total_ny_paid, ye_total_ny_paid, is_bold=True
    )
    render_row("NJ Tax Withheld from Bombas W-2", act_nj_withheld_w2, ye_nj_withheld_w2)
    render_row("NJ Tax Estimated Payments Paid", act_nj_estimated, ye_nj_estimated)
    render_row(
        "Total NJ State Taxes Paid So Far", act_total_nj_paid, ye_total_nj_paid, is_bold=True
    )

    render_row("FINAL TAX CALCULATOR & LIABILITY BALANCE", "", "", is_header=True)
    render_row("Schedule C SE Tax Modifier", se_modifier, se_modifier)
    render_row("Net Earnings Subject to SE Tax", act_se_subject, ye_se_subject)
    render_row("Calculated Self-Employment Tax", act_se_tax_val, ye_se_tax_val)
    render_row("Half of SE Tax Deduction", act_half_se, ye_half_se)
    render_row("401k Contributions", act_401k_contribs, ye_401k_contribs)
    render_row("HSA Contributions", act_hsa_contribs, ye_hsa_contribs)
    render_row("Adjusted Gross Income (AGI)", act_agi, ye_agi, is_bold=True)
    render_row("2026 Standard Deduction (MFJ)", std_deduction, std_deduction)
    render_row(
        "Total Estimated Federal Taxable Income", act_taxable_inc, ye_taxable_inc, is_bold=True
    )
    render_row("Calculated Federal Income Tax", act_fed_tax_val, ye_fed_tax_val)
    render_row("TOTAL FEDERAL BALANCE DUE / (REFUND)", act_fed_bal, ye_fed_bal, is_bold=True)
    render_row("New York", "", "", is_bold=True)
    render_row("NY AGI", act_w2_gross, ye_w2_gross)
    render_row("529 Contribution", act_529_contribs, ye_529_contribs)
    render_row("Calculated NY State Income Tax", act_ny_tax_val, ye_ny_tax_val)
    render_row("TOTAL NY STATE BALANCE DUE / (REFUND)", act_ny_bal, ye_ny_bal, is_bold=True)
    render_row("New Jersey", "", "", is_bold=True)
    render_row("Calculated Gross NJ State Income Tax", act_nj_gross_tax, ye_nj_gross_tax)
    render_row("Calculated NJ Credit for NY Taxes Paid", act_nj_credit, ye_nj_credit)
    render_row("Net NJ State Tax Liability", act_nj_net, ye_nj_net)
    render_row("TOTAL NJ STATE BALANCE DUE / (REFUND)", act_nj_bal, ye_nj_bal, is_bold=True)

with tab2:
    st.markdown(
        '<div class="main-header">Underlying Transactions Ledger</div>', unsafe_allow_html=True
    )
    st.dataframe(ledger_df, width="stretch")
