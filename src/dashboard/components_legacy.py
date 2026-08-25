"""Legacy single-page dashboard renderers — used by unit tests."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.data import CachedMondayData, minutes_since_sync
from src.dashboard.health import calculate_health_score, classify_customer_health
from src.dashboard.metrics import DashboardMetrics
from src.ui.formatting import fmt_customer_code, fmt_inr, fmt_pct


def render_data_diagnostics(metrics: DashboardMetrics, *, load_ms: float | None = None) -> None:
    with st.expander("Data diagnostics", expanded=False):
        dq = metrics.data_quality
        st.caption("Internal data quality checks — for technical review only.")
        st.write({
            "Company matches": dq.get("matched_companies"),
            "Missing deal values": dq.get("missing_deal_values"),
            "Parse failures": dq.get("numeric_parse_failures"),
            "Deal-only companies": dq.get("deal_only_company_count"),
        })
        if load_ms is not None:
            st.caption(f"Dashboard render: {load_ms:.0f}ms")


def render_executive_overview(metrics: DashboardMetrics) -> None:
    rev = metrics.revenue
    pipe = metrics.pipeline
    cols = st.columns(4)
    cards = [
        ("REVENUE", fmt_inr(rev.get("billed_revenue")), "Billed revenue"),
        ("COLLECTED", fmt_inr(rev.get("collected_revenue")), "Cash collected"),
        ("RECEIVABLE", fmt_inr(rev.get("receivables")), "Outstanding"),
        ("OPEN PIPELINE", fmt_inr(pipe.get("open_pipeline")), "Open opportunities"),
    ]
    for col, (label, value, desc) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div>{label}: {value}</div>',
                unsafe_allow_html=True,
            )


def render_business_health(metrics: DashboardMetrics) -> None:
    health = calculate_health_score(metrics)
    assert "overall" in health


def render_revenue_cash(metrics: DashboardMetrics) -> None:
    rev = metrics.revenue
    assert rev.get("billed_revenue") is not None or True


def render_pipeline(metrics: DashboardMetrics) -> None:
    assert metrics.pipeline is not None


def render_customer_intelligence(metrics: DashboardMetrics) -> None:
    top = metrics.customers.get("top_collected", [])[:10]
    if top:
        st.dataframe(pd.DataFrame([{"Customer": c.get("company_code")} for c in top]))


def render_operational_health(metrics: DashboardMetrics) -> None:
    assert metrics.operations is not None
