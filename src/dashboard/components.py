"""Skylark Founder's Dashboard UI components."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.data import CachedMondayData, minutes_since_sync
from src.dashboard.health import calculate_health_score, classify_customer_health
from src.dashboard.metrics import DashboardMetrics
from src.ui.formatting import fmt_customer_code, fmt_inr, fmt_pct, health_badge


def render_header(data: CachedMondayData, *, data_ok: bool) -> bool:
    """Render header; returns True if refresh was requested."""
    sync_mins = minutes_since_sync(data.loaded_at)
    sync_label = f"{int(sync_mins)} min ago" if sync_mins >= 1 else "just now"
    live = '<span class="sk-live">LIVE DATA ●</span>' if data_ok else "Data sync pending"
    left, right = st.columns([5, 1])
    with left:
        st.markdown(
            f"""
<div class="sk-header">
  <div>
    <div class="sk-title">SKYLARK FOUNDER'S DASHBOARD</div>
    <div class="sk-subtitle">Executive business intelligence powered by live operational data</div>
  </div>
  <div class="sk-meta">
    {live}<br>
    Last updated: {sync_label}
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
        if st.button("Refresh", type="primary", use_container_width=True, key="sk_refresh"):
            return True
    return False


def _kpi_card(label: str, value: str, desc: str) -> str:
    return (
        f'<div class="sk-kpi-card">'
        f'<div class="sk-kpi-label">{label}</div>'
        f'<div class="sk-kpi-value">{value}</div>'
        f'<div class="sk-kpi-desc">{desc}</div></div>'
    )


def render_executive_overview(metrics: DashboardMetrics) -> None:
    st.markdown('<div class="sk-section">Executive Overview</div>', unsafe_allow_html=True)
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
            st.markdown(_kpi_card(label, value, desc), unsafe_allow_html=True)


def render_business_health(metrics: DashboardMetrics) -> None:
    health = calculate_health_score(metrics)
    st.markdown('<div class="sk-section">Business Health</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        st.markdown(
            f'<div class="sk-kpi-card"><div class="sk-kpi-label">BUSINESS HEALTH</div>'
            f'<div class="sk-health-score">{health["overall"]:.0f} <span style="font-size:1rem;color:#7a8a9a">/ 100</span></div></div>',
            unsafe_allow_html=True,
        )
    breakdown = health.get("breakdown", {})
    drivers = [
        ("Revenue Health", breakdown.get("revenue_health", 0)),
        ("Pipeline Health", breakdown.get("pipeline_health", 0)),
        ("Collection Health", breakdown.get("collections_health", 0)),
    ]
    for col, (name, score) in zip([c2, c3, c4], drivers):
        with col:
            st.markdown(f"**{name}**")
            st.progress(min(int(score) / 100, 1.0) if score else 0)


def render_revenue_cash(metrics: DashboardMetrics) -> None:
    st.markdown('<div class="sk-section">Revenue & Cash</div>', unsafe_allow_html=True)
    rev = metrics.revenue
    c1, c2 = st.columns([1, 1])
    with c1:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Billed", fmt_inr(rev.get("billed_revenue")))
        m2.metric("Collected", fmt_inr(rev.get("collected_revenue")))
        m3.metric("Receivable", fmt_inr(rev.get("receivables")))
        m4.metric("Collection Rate", fmt_pct(rev.get("collection_rate")))
    with c2:
        billed = rev.get("billed_revenue") or 0
        collected = rev.get("collected_revenue") or 0
        outstanding = rev.get("receivables") or 0
        if billed > 0:
            df = pd.DataFrame({
                "Stage": ["Billed", "Collected", "Outstanding"],
                "Amount": [billed, collected, outstanding],
            })
            st.caption("Billed → Collected → Outstanding")
            st.bar_chart(df.set_index("Stage")["Amount"])


def _pipeline_concentration(stages: list[dict]) -> str | None:
    if not stages:
        return None
    sorted_stages = sorted(stages, key=lambda g: g.get("pipeline_value") or 0, reverse=True)
    total = sum(g.get("pipeline_value") or 0 for g in sorted_stages)
    if total <= 0:
        return None
    top_n = min(3, len(sorted_stages))
    top_val = sum(g.get("pipeline_value") or 0 for g in sorted_stages[:top_n])
    pct = top_val / total * 100
    return f"{pct:.0f}% of open pipeline is concentrated in the top {top_n} stage{'s' if top_n > 1 else ''}."


def render_pipeline(metrics: DashboardMetrics) -> None:
    st.markdown('<div class="sk-section">Pipeline</div>', unsafe_allow_html=True)
    pipe = metrics.pipeline
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Deals", pipe.get("open_deal_count") or "—")
    c2.metric("Open Pipeline", fmt_inr(pipe.get("open_pipeline")))
    c3.metric("Weighted Pipeline", fmt_inr(pipe.get("weighted_pipeline")))
    c4.metric("Avg Deal Value", fmt_inr(pipe.get("avg_deal_value")))

    stages = pipe.get("stages", [])
    if stages:
        df = pd.DataFrame([
            {
                "Stage": (g.get("deal_stage") or "Unknown")[:28],
                "Value": g.get("pipeline_value") or 0,
            }
            for g in stages
        ]).sort_values("Value", ascending=True)
        st.caption("Pipeline by deal stage")
        st.bar_chart(df.set_index("Stage")["Value"])

        insight = _pipeline_concentration(stages)
        if insight:
            st.markdown(f'<div class="sk-insight"><strong>Pipeline concentration</strong> — {insight}</div>', unsafe_allow_html=True)


def _customer_table_rows(customers: list[dict], limit: int) -> pd.DataFrame:
    rows = []
    for c in customers[:limit]:
        health = classify_customer_health(c)
        rows.append({
            "Customer": fmt_customer_code(c.get("company_code")),
            "Collected": fmt_inr(c.get("collected")),
            "Receivable": fmt_inr(c.get("receivables")),
            "Pipeline": fmt_inr(c.get("open_pipeline")),
            "Work Orders": c.get("work_orders") or 0,
            "Health": health,
        })
    return pd.DataFrame(rows)


def render_customer_intelligence(metrics: DashboardMetrics) -> None:
    st.markdown('<div class="sk-section">Customer Intelligence</div>', unsafe_allow_html=True)
    top = metrics.customers.get("top_collected", [])[:10]
    if top:
        st.markdown("**Top Customers**")
        st.dataframe(_customer_table_rows(top, 10), hide_index=True, use_container_width=True, height=320)

    attention = metrics.customers.get("rankings", {}).get("attention", {}).get("customers", [])[:8]
    receivables_top = metrics.customers.get("rankings", {}).get("receivables", {}).get("customers", [])[:5]
    seen = {c.get("company_code") for c in attention}
    for c in receivables_top:
        if c.get("company_code") not in seen and len(attention) < 8:
            attention.append(c)
            seen.add(c.get("company_code"))

    if attention:
        st.markdown("**Customers Requiring Attention**")
        att_rows = []
        for c in attention[:8]:
            att_rows.append({
                "Customer": fmt_customer_code(c.get("company_code")),
                "Receivable": fmt_inr(c.get("receivables")),
                "Pipeline": fmt_inr(c.get("open_pipeline")),
                "Health": classify_customer_health(c),
            })
        st.dataframe(pd.DataFrame(att_rows), hide_index=True, use_container_width=True, height=220)


def _billing_issues(ops: dict) -> int:
    total = 0
    for g in ops.get("billing_status", []):
        status = str(g.get("billing_status", "")).lower()
        if status and status not in ("billed", "completed", "done", "paid", "none", ""):
            total += g.get("count", 0)
    return total


def render_operational_health(metrics: DashboardMetrics) -> None:
    st.markdown('<div class="sk-section">Operational Health</div>', unsafe_allow_html=True)
    ops = metrics.operations
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Work Orders", ops.get("open_work_orders") or 0)
    c2.metric("Completed", ops.get("completed") or 0)
    attention = (ops.get("not_started") or 0) + (ops.get("stuck") or 0)
    c3.metric("Requiring Attention", attention)
    c4.metric("Billing / Collection Issues", _billing_issues(ops))

    exec_status = ops.get("execution_status", [])
    if exec_status:
        df = pd.DataFrame([
            {"Status": (g.get("execution_status") or "Unknown")[:24], "Count": g.get("count", 0)}
            for g in sorted(exec_status, key=lambda x: x.get("count", 0), reverse=True)[:6]
        ])
        st.bar_chart(df.set_index("Status")["Count"])


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


def render_skylark_dashboard(
    data: CachedMondayData,
    metrics: DashboardMetrics,
    *,
    data_ok: bool,
    debug_mode: bool = False,
    load_ms: float | None = None,
) -> bool:
    """Single-page executive dashboard. Returns True if refresh requested."""
    if not data_ok:
        st.warning("Some live data is temporarily unavailable. Please refresh.")

    if render_header(data, data_ok=data_ok):
        return True

    render_executive_overview(metrics)
    render_business_health(metrics)
    render_revenue_cash(metrics)
    render_pipeline(metrics)
    render_customer_intelligence(metrics)
    render_operational_health(metrics)

    if debug_mode:
        render_data_diagnostics(metrics, load_ms=load_ms)
    else:
        with st.expander("Data diagnostics", expanded=False):
            st.caption("Data quality checks: available")

    return False


# Legacy aliases
render_full_dashboard = render_skylark_dashboard
render_customer_command = render_customer_intelligence
render_pipeline_command = render_pipeline
render_operations_command = render_operational_health
