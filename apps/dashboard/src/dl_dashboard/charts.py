"""Plotly chart builders for the dashboard (no Streamlit side effects)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_SANKEY_PALETTE = px.colors.qualitative.Set3 + px.colors.qualitative.Pastel


def _rgba(color: str, alpha: float) -> str:
    """Convert a plotly '#rrggbb' or 'rgb(r,g,b)' color to an rgba() string."""
    if color.startswith("#"):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    else:
        r, g, b = (int(x) for x in color.removeprefix("rgb(").removesuffix(")").split(","))
    return f"rgba({r},{g},{b},{alpha})"


def cashflow_sankey(df: pd.DataFrame) -> go.Figure | None:
    """Income category → income group → expense group → expense category.

    The middle tier (income group → expense group) has no natural per-pair
    mapping since money is fungible, so each income group is split across the
    expense groups proportionally to their size. A Savings node absorbs the
    income that was not spent, keeping every node's inflow equal to its outflow.

    Node labels carry the dollar throughput and its share: income and savings
    nodes as a share of total income, spend nodes as a share of total expense.
    """
    income = df[df["income_amount"] > 0]
    expense = df[df["spend_amount"] > 0]
    total_income = float(income["income_amount"].sum())
    total_expense = float(expense["spend_amount"].sum())
    if total_income <= 0 or total_expense <= 0:
        return None

    inc_by_cat = income.groupby(["category_name", "category_group"], as_index=False)[
        "income_amount"
    ].sum()
    exp_by_cat = expense.groupby(["category_group", "category_name"], as_index=False)[
        "spend_amount"
    ].sum()
    inc_grp_totals = income.groupby("category_group", as_index=False)["income_amount"].sum()
    exp_grp_totals = expense.groupby("category_group", as_index=False)["spend_amount"].sum()
    savings = max(0.0, total_income - total_expense)

    # Collapse sub-threshold leaf categories into a per-group "Other" so the
    # chart is not crowded with slivers. Grouping keeps totals unchanged.
    def _bucket(frame: pd.DataFrame, amount_col: str, floor: float) -> pd.DataFrame:
        display = [
            r.category_name if getattr(r, amount_col) >= floor else "Other"
            for r in frame.itertuples(index=False)
        ]
        out = frame.assign(category_name=display)
        return out.groupby(["category_group", "category_name"], as_index=False)[amount_col].sum()

    inc_by_cat = _bucket(inc_by_cat, "income_amount", 0.01 * total_income)
    exp_by_cat = _bucket(exp_by_cat, "spend_amount", 0.01 * total_expense)

    # Prefixes keep node names unique across the four tiers. `side` drives which
    # denominator a node's percentage uses.
    names: list[str] = []
    sides: list[str] = []
    index: dict[str, int] = {}

    def node(key: str, label: str, side: str) -> int:
        if key not in index:
            index[key] = len(names)
            names.append(label)
            sides.append(side)
        return index[key]

    src: list[int] = []
    dst: list[int] = []
    val: list[float] = []

    # Tier 1: income category → income group.
    for row in inc_by_cat.itertuples(index=False):
        cat, grp = str(row.category_name), str(row.category_group)
        src.append(node(f"ic::{cat}", cat, "income"))
        dst.append(node(f"ig::{grp}", grp, "income"))
        val.append(float(row.income_amount))

    # Tier 2: every income group funnels into a single Income Pool, which then
    # fans out to the expense groups (+ Savings). The pool avoids drawing a link
    # from each income group to each expense group.
    pool = node("pool", "Income Pool", "income")
    for ig in inc_grp_totals.itertuples(index=False):
        src.append(node(f"ig::{ig.category_group}", str(ig.category_group), "income"))
        dst.append(pool)
        val.append(float(ig.income_amount))
    for eg in exp_grp_totals.itertuples(index=False):
        src.append(pool)
        dst.append(node(f"eg::{eg.category_group}", str(eg.category_group), "expense"))
        val.append(float(eg.spend_amount))
    if savings > 0:
        src.append(pool)
        dst.append(node("savings", "Savings", "savings"))
        val.append(savings)

    # Tier 3: expense group → expense category. Keys are group-qualified so a
    # per-group "Other" bucket stays distinct from another group's.
    for row in exp_by_cat.itertuples(index=False):
        grp, cat = str(row.category_group), str(row.category_name)
        src.append(node(f"eg::{grp}", grp, "expense"))
        dst.append(node(f"ec::{grp}::{cat}", cat, "expense"))
        val.append(float(row.spend_amount))

    # Per-node throughput = incoming flow (fall back to outgoing for the income
    # categories, which have no inflow).
    n = len(names)
    incoming = [0.0] * n
    outgoing = [0.0] * n
    for s, d, v in zip(src, dst, val, strict=True):
        outgoing[s] += v
        incoming[d] += v
    totals = [incoming[i] if incoming[i] > 0 else outgoing[i] for i in range(n)]

    # Labels carry the dollar value + share; colors are stable per name.
    color_map: dict[str, str] = {}

    def color_for(name: str) -> str:
        if name not in color_map:
            color_map[name] = _SANKEY_PALETTE[len(color_map) % len(_SANKEY_PALETTE)]
        return color_map[name]

    labels: list[str] = []
    node_colors: list[str] = []
    for i in range(n):
        denom = total_expense if sides[i] == "expense" else total_income
        pct = totals[i] / denom if denom else 0.0
        labels.append(f"{names[i]}<br>${totals[i]:,.2f} ({pct:.2%})")
        node_colors.append(color_for(names[i]))
    link_colors = [_rgba(node_colors[s], 0.4) for s in src]

    # Height scales with the busiest tier so leaf nodes are not bunched.
    leaves = max(
        sides.count("income"),
        sides.count("expense") + sides.count("savings"),
        1,
    )
    height = max(650, 34 * leaves)

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            # Explicit label font + no shadow so text stays legible over nodes.
            textfont=dict(color="black", size=13, shadow="none"),
            node=dict(label=labels, color=node_colors, pad=26, thickness=18, line_width=0),
            link=dict(source=src, target=dst, value=val, color=link_colors),
        )
    )
    fig.update_layout(
        margin=dict(t=10, b=10, l=0, r=0),
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig
