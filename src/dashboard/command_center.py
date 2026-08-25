"""SKYLARK // FOUNDER INTELLIGENCE — tabbed command center UI."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.customer_tiers import classify_customer_tier
from src.dashboard.data import CachedMondayData, minutes_since_sync
from src.dashboard.founder_brief import generate_founder_brief
from src.dashboard.health import classify_customer_health
from src.dashboard.intelligence_engine import IntelligenceBundle, build_intelligence
from src.dashboard.metrics import DashboardMetrics
from src.tools.pipeline_analysis import pipeline_analysis_tool
from src.ui.formatting import fmt_customer_code, fmt_inr, fmt_pct


TABS = [
    "OVERVIEW",
    "REVENUE & CASH",
    "PIPELINE",
    "CUSTOMERS",
    "OPERATIONS",
    "SECTORS",
    "RISKS & OPPORTUNITIES",
    "DATA HEALTH",
    "ASK SKYLARK",
]

RISK_LABELS = {
    "CASH_RISK": "CASH RISK",
    "CUSTOMER_RISK": "CUSTOMER RISK",
    "PIPELINE_RISK": "PIPELINE RISK",
    "OPERATIONAL_RISK": "OPERATIONAL RISK",
    "DATA_RISK": "DATA RISK",
}

OPP_LABELS = {
    "LARGE_PIPELINE": "LARGE PIPELINE",
    "LARGE_CUSTOMERS": "LARGE CUSTOMERS",
    "HIGH_VALUE_DEALS": "HIGH-VALUE OPEN DEALS",
    "SECTOR_OPPORTUNITIES": "SECTOR OPPORTUNITIES",
    "CROSS_SELL": "CROSS-SELL OPPORTUNITIES",
}


def render_header(data: CachedMondayData, *, data_ok: bool) -> bool:
    sync_mins = minutes_since_sync(data.loaded_at)
    sync_label = f"{int(sync_mins)} min ago" if sync_mins >= 1 else "just now"
    live = '<span class="fi-live">● LIVE</span>' if data_ok else "SYNC PENDING"
    left, right = st.columns([5, 1])
    with left:
        st.markdown(
            f"""
<div class="fi-header">
  <div class="fi-title">SKYLARK // FOUNDER INTELLIGENCE</div>
  <div class="fi-sub">Business intelligence command center</div>
  <div class="fi-meta">{live} &nbsp;·&nbsp; Updated {sync_label}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
        if st.button("REFRESH", type="primary", use_container_width=True, key="fi_refresh"):
            return True
    return False


def _kpi(label: str, value: str, hint: str = "", caveat: str = "") -> None:
    caveat_html = f'<div class="fi-kpi-caveat">⚠ {caveat}</div>' if caveat else ""
    st.markdown(
        f'<div class="fi-kpi"><div class="fi-kpi-label">{label}</div>'
        f'<div class="fi-kpi-value">{value}</div>'
        f'<div class="fi-kpi-hint">{hint}</div>{caveat_html}</div>',
        unsafe_allow_html=True,
    )


def _section(title: str) -> None:
    st.markdown(f'<div class="fi-section">{title}</div>', unsafe_allow_html=True)


def _insight_card(item: dict[str, Any]) -> None:
    sev = item.get("severity", "")
    cls = "fi-risk" if sev in ("HIGH", "MEDIUM") else "fi-opp"
    st.markdown(
        f'<div class="fi-insight {cls}">'
        f'<div class="fi-insight-title">{item.get("title", "")}</div>'
        f'<div class="fi-insight-metric">{item.get("metric", "")}</div>'
        f'<div class="fi-insight-body">{item.get("explanation", "")}</div>'
        f'<div class="fi-insight-action">ACTION: {item.get("action", "")}</div></div>',
        unsafe_allow_html=True,
    )


def _confidence_badge(confidence: str) -> str:
    cls = {"HIGH": "fi-conf-high", "MEDIUM": "fi-conf-medium", "LOW": "fi-conf-low"}.get(
        confidence, "fi-conf-medium"
    )
    return f'<span class="fi-confidence {cls}">{confidence}</span>'


def render_data_integrity_strip(dq: dict[str, Any], *, expanded: bool = False) -> None:
    """Compact executive data integrity summary."""
    conf = dq.get("confidence", "MEDIUM")
    st.markdown(
        f'<div class="fi-integrity-strip">'
        f'<span class="fi-section-inline">DATA INTEGRITY</span> '
        f'{_confidence_badge(conf)}</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f'<span class="fi-mono-sm">Records</span><br><b>{dq.get("records_analyzed", 0)}</b>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<span class="fi-mono-sm">Complete</span><br><b>{dq.get("complete_records", 0)}</b>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<span class="fi-mono-sm">Incomplete</span><br><b>{dq.get("incomplete_records", 0)}</b>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<span class="fi-mono-sm">Parse issues</span><br><b>{dq.get("parse_issues", 0)}</b>', unsafe_allow_html=True)
    with c5:
        st.markdown(
            f'<span class="fi-mono-sm">Missing collections</span><br><b>{dq.get("missing_collections", 0)}</b>',
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            f'<span class="fi-mono-sm">Cross-board</span><br><b>{dq.get("cross_board_matches", 0)}</b>',
            unsafe_allow_html=True,
        )
    with st.expander("View diagnostics →", expanded=expanded):
        for reason in dq.get("confidence_reasons", []):
            st.caption(f"• {reason}")
        diag = dq.get("diagnostics", [])
        if diag:
            st.dataframe(pd.DataFrame(diag), hide_index=True, use_container_width=True, height=160)


def _render_founder_brief(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    brief = generate_founder_brief(metrics, intel)
    st.markdown(f"### {brief['title']}")
    st.caption(brief.get("snapshot_note", ""))
    st.caption(f"Data confidence: **{brief.get('data_confidence', '—')}**")

    fin = brief.get("financial", {})
    st.markdown(
        f"**FINANCIAL** — Billed {fin.get('billed_revenue')} · Collected {fin.get('collected')} · "
        f"Receivables {fin.get('receivables')} · Collection {fin.get('collection_rate_pct')}% · "
        f"Pipeline {fin.get('open_pipeline')} ({fin.get('open_deals')} deals)"
    )
    cust = brief.get("customers", {})
    at_risk = ", ".join(
        f"{a['customer']} ({a['receivables']})" for a in cust.get("at_risk", [])
    ) or "None flagged"
    st.markdown(
        f"**CUSTOMERS** — Top: {cust.get('top_customer')} ({cust.get('top_collected')}) · At risk: {at_risk}"
    )
    ops = brief.get("operations", {})
    st.markdown(
        f"**OPERATIONS** — Stuck WOs: {ops.get('stuck_work_orders')} · "
        f"Bottleneck: {ops.get('bottleneck') or 'None detected'}"
    )
    sec = brief.get("sectors", {})
    st.markdown(f"**SECTORS** — Top: {sec.get('top_sector')} (pipeline {sec.get('top_pipeline')})")

    st.markdown("**RISKS**")
    for r in brief.get("risks", []):
        st.markdown(f"- {r.get('title')}: {r.get('metric')} — {r.get('action')}")

    st.markdown("**OPPORTUNITIES**")
    for o in brief.get("opportunities", []):
        st.markdown(f"- {o.get('title')}: {o.get('metric')} — {o.get('action')}")

    st.markdown("**FOUNDER ACTIONS**")
    for a in brief.get("founder_actions", []):
        st.markdown(f"{a.get('rank', 0):02d} — **{a.get('category', '')}** — {a.get('detail', '')}")

    for c in brief.get("caveats", []):
        st.caption(f"⚠ {c}")


def tab_overview(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    rev, pipe = metrics.revenue, metrics.pipeline
    health = intel.health
    dq = intel.data_integrity
    caveats = dq.get("caveats", {})

    render_data_integrity_strip(dq)

    brief_col1, brief_col2 = st.columns([3, 1])
    with brief_col2:
        if st.button("GENERATE FOUNDER BRIEF", use_container_width=True, key="founder_brief_btn"):
            st.session_state["show_founder_brief"] = True
    if st.session_state.get("show_founder_brief"):
        with st.expander("FOUNDER BRIEF", expanded=True):
            _render_founder_brief(metrics, intel)
            if st.button("Close brief", key="close_brief"):
                st.session_state["show_founder_brief"] = False
                st.rerun()

    _section("BUSINESS HEALTH")
    hc1, hc2 = st.columns([1, 4])
    with hc1:
        _kpi("OVERALL HEALTH", f"{health.get('overall', 0):.0f} / 100", "Composite score")
    with hc2:
        bd = health.get("breakdown", {})
        d1, d2, d3, d4 = st.columns(4)
        drivers = [
            ("Revenue Health", bd.get("revenue_health", 0)),
            ("Collection Health", bd.get("collections_health", 0)),
            ("Pipeline Health", bd.get("pipeline_health", 0)),
            ("Operational Health", bd.get("operations_health", 0)),
        ]
        for col, (name, score) in zip([d1, d2, d3, d4], drivers):
            with col:
                st.markdown(f'<span class="fi-driver-label">{name}</span>', unsafe_allow_html=True)
                st.progress(min(float(score) / 100, 1.0) if score else 0)

    _section("FINANCIAL POSITION")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        _kpi("BILLED REVENUE", fmt_inr(rev.get("billed_revenue")), "REVENUE = BILLED")
    with f2:
        _kpi("COLLECTED", fmt_inr(rev.get("collected_revenue")), "Cash realized", caveats.get("collection_rate", ""))
    with f3:
        _kpi("RECEIVABLES", fmt_inr(rev.get("receivables")), "Outstanding AR", caveats.get("receivables", ""))
    with f4:
        _kpi("COLLECTION RATE", fmt_pct(rev.get("collection_rate")), "", caveats.get("collection_rate", ""))

    _section("GROWTH ENGINE")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        _kpi("OPEN PIPELINE", fmt_inr(pipe.get("open_pipeline")), caveats.get("pipeline", ""))
    with g2:
        _kpi("OPEN DEALS", str(pipe.get("open_deal_count") or "—"))
    with g3:
        _kpi("WEIGHTED PIPELINE", fmt_inr(pipe.get("weighted_pipeline")))
    with g4:
        avg = pipe.get("average_deal_size")
        _kpi("AVG DEAL SIZE", fmt_inr(avg) if avg else "—")

    _section("CUSTOMER POSITION")
    conc = intel.customer_concentration
    rows = metrics.customers.get("rows") or []
    at_risk = sum(1 for r in rows if classify_customer_health(r) == "AT RISK")
    watch = sum(1 for r in rows if classify_customer_health(r) == "WATCH")
    cp1, cp2, cp3, cp4 = st.columns(4)
    with cp1:
        share = conc.get("share_pct")
        _kpi("TOP CONCENTRATION", f"{share}%" if share else "—", f"Top {conc.get('top_n', 5)} customers")
    with cp2:
        _kpi("AT RISK", str(at_risk))
    with cp3:
        _kpi("REQUIRING ATTENTION", str(at_risk + watch))
    with cp4:
        top_ar = max((r.get("receivables") or 0 for r in rows), default=0)
        _kpi("MAX RECEIVABLE", fmt_inr(top_ar) if top_ar else "—")

    _section("OPERATIONAL POSITION")
    ops = metrics.operations
    op1, op2, op3, op4 = st.columns(4)
    with op1:
        _kpi("OPEN WOs", str(ops.get("open_work_orders") or 0))
    with op2:
        _kpi("COMPLETED", str(ops.get("completed") or 0))
    with op3:
        _kpi("STUCK / DELAYED", str(ops.get("stuck") or 0))
    with op4:
        billing_issues = sum(1 for r in intel.operations_risks if r.get("type") == "completed_unbilled")
        _kpi("BILLING ISSUES", str(billing_issues))

    _section("FOUNDER PRIORITIES")
    for action in intel.founder_actions[:5]:
        st.markdown(
            f'**{action.get("rank", 0):02d}** — '
            f'<span class="fi-mono">{action.get("category", "")}</span> — '
            f'{action.get("detail", "")}',
            unsafe_allow_html=True,
        )

    left, right = st.columns(2)
    with left:
        _section("RISK MONITOR")
        for r in intel.risks[:4]:
            _insight_card(r)
    with right:
        _section("OPPORTUNITY RADAR")
        for o in intel.opportunities[:4]:
            _insight_card(o)

    st.caption(dq.get("live_snapshot_note", ""))


def tab_revenue(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    rev = metrics.revenue
    gaps = intel.revenue_gaps
    caveats = intel.data_integrity.get("caveats", {})

    st.caption("REVENUE = BILLED REVENUE — not contract + billed + collected combined")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _kpi("CONTRACT VALUE", fmt_inr(rev.get("contract_value")))
    with c2:
        _kpi("BILLED REVENUE", fmt_inr(rev.get("billed_revenue")), "Primary revenue metric")
    with c3:
        _kpi("COLLECTED", fmt_inr(rev.get("collected_revenue")), "", caveats.get("collection_rate", ""))
    with c4:
        _kpi("RECEIVABLES", fmt_inr(rev.get("receivables")), "Source field sum", caveats.get("receivables", ""))
    with c5:
        _kpi("COLLECTION RATE", fmt_pct(rev.get("collection_rate")), "", caveats.get("collection_rate", ""))

    left, right = st.columns(2)
    with left:
        _section("FINANCIAL FLOW")
        st.markdown(
            '<div class="fi-flow">CONTRACT<br>↓<br>BILLED<br>↓<br>COLLECTED</div>',
            unsafe_allow_html=True,
        )
        df = pd.DataFrame({
            "Stage": ["Contract", "Billed", "Collected"],
            "Amount": [
                gaps.get("contract_value") or 0,
                gaps.get("billed_revenue") or 0,
                gaps.get("collected_revenue") or 0,
            ],
        })
        st.bar_chart(df.set_index("Stage")["Amount"], height=200)
        if gaps.get("unbilled_gap"):
            st.caption(f"Unbilled gap (contract − billed): {fmt_inr(gaps['unbilled_gap'])}")
        if gaps.get("uncollected_from_billed"):
            st.caption(f"Uncollected from billed: {fmt_inr(gaps['uncollected_from_billed'])}")
        st.caption("Receivables shown separately from billed − collected (source field).")
    with right:
        _section("TOP RECEIVABLE CUSTOMERS")
        rows = sorted(
            metrics.customers.get("rows") or [],
            key=lambda r: r.get("receivables") or 0,
            reverse=True,
        )[:8]
        if rows:
            st.dataframe(pd.DataFrame([
                {
                    "Customer": fmt_customer_code(r.get("company_code")),
                    "Receivable": fmt_inr(r.get("receivables")),
                    "Collected": fmt_inr(r.get("collected")),
                    "Health": classify_customer_health(r),
                }
                for r in rows
            ]), hide_index=True, use_container_width=True, height=280)


def tab_pipeline(metrics: DashboardMetrics, intel: IntelligenceBundle, data_service) -> None:
    pipe = metrics.pipeline
    radar = intel.pipeline_radar
    caveats = intel.data_integrity.get("caveats", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _kpi("OPEN PIPELINE", fmt_inr(pipe.get("open_pipeline")), caveats.get("pipeline", ""))
    with c2:
        _kpi("WEIGHTED", fmt_inr(pipe.get("weighted_pipeline")))
    with c3:
        _kpi("OPEN DEALS", str(pipe.get("open_deal_count") or "—"))
    with c4:
        _kpi("STALE DEALS", str(pipe.get("stale_open_deals") or 0))
    with c5:
        largest = radar.get("largest_opportunity") or {}
        _kpi("LARGEST OPP.", fmt_inr(largest.get("deal_value")), (largest.get("deal_name") or "")[:28])

    st.caption(intel.data_integrity.get("live_snapshot_note", ""))

    filt_l, filt_r = st.columns([1, 1])
    with filt_l:
        sector_filter = st.selectbox(
            "Sector filter",
            ["All", "Energy", "Renewables", "Mining", "Construction", "Aviation"],
            key="pipe_sector",
        )
    with filt_r:
        period_filter = st.selectbox(
            "Period",
            ["All", "this_quarter", "this_month", "this_week", "this_year"],
            key="pipe_period",
        )

    if sector_filter != "All" or period_filter != "All":
        result = pipeline_analysis_tool(
            data_service,
            sector=None if sector_filter == "All" else sector_filter,
            period=None if period_filter == "All" else period_filter,
        )
        st.caption(f"Filtered: {result.get('sector') or 'All sectors'} · {result.get('period') or 'All time'}")
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Filtered deals", result.get("open_deal_count"))
        fc2.metric("Pipeline", fmt_inr(result.get("pipeline_inr")))
        fc3.metric("Weighted", fmt_inr(result.get("weighted_pipeline_inr")))
        if result.get("data_quality_caveats"):
            st.caption(f"⚠ {result['data_quality_caveats'][0]}")

    left, right = st.columns(2)
    with left:
        _section("PIPELINE BY STAGE")
        stages = pipe.get("stages", [])
        if stages:
            df = pd.DataFrame([
                {"Stage": (g.get("deal_stage") or "?")[:24], "Value": g.get("pipeline_value") or 0}
                for g in sorted(stages, key=lambda x: x.get("pipeline_value") or 0)
            ])
            st.bar_chart(df.set_index("Stage")["Value"], height=220)
    with right:
        _section("PIPELINE BY SECTOR")
        by_pipe = metrics.sectors.get("by_pipeline", [])[:8]
        if by_pipe:
            df = pd.DataFrame([
                {"Sector": (g.get("sector_normalized") or "?")[:16], "Pipeline": g.get("pipeline") or 0}
                for g in by_pipe
            ])
            st.bar_chart(df.set_index("Sector")["Pipeline"], height=220)

    _section("OPPORTUNITY RADAR")
    counts = radar.get("counts", {})
    r1, r2, r3, r4 = st.columns(4)
    for col, label in zip([r1, r2, r3, r4], ("HIGH VALUE", "QUICK WIN", "STALE", "AT RISK")):
        with col:
            _kpi(label, str(counts.get(label, 0)))


def tab_customers(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    conc = intel.customer_concentration
    rows = metrics.customers.get("rows") or []

    c1, c2, c3 = st.columns(3)
    with c1:
        share = conc.get("share_pct")
        _kpi("TOP CONCENTRATION", f"{share}%" if share else "—", f"Top {conc.get('top_n', 5)} by collected")
    with c2:
        at_risk = [r for r in rows if classify_customer_health(r) == "AT RISK"]
        _kpi("CUSTOMERS AT RISK", str(len(at_risk)))
    with c3:
        watch = [r for r in rows if classify_customer_health(r) == "WATCH"]
        _kpi("REQUIRING ATTENTION", str(len(at_risk) + len(watch)))

    left, right = st.columns(2)
    with left:
        _section("TOP CUSTOMERS — COLLECTED")
        top_col = sorted(rows, key=lambda r: r.get("collected") or 0, reverse=True)[:6]
        for r in top_col:
            st.markdown(
                f"**{fmt_customer_code(r.get('company_code'))}** — "
                f"{fmt_inr(r.get('collected'))} · {r.get('health', classify_customer_health(r))}"
            )
    with right:
        _section("TOP RECEIVABLE CUSTOMERS")
        top_ar = sorted(rows, key=lambda r: r.get("receivables") or 0, reverse=True)[:6]
        for r in top_ar:
            st.markdown(
                f"**{fmt_customer_code(r.get('company_code'))}** — "
                f"AR {fmt_inr(r.get('receivables'))} · {classify_customer_health(r)}"
            )

    _section("CUSTOMER RISK RADAR")
    attention = sorted(
        [r for r in rows if classify_customer_health(r) in ("AT RISK", "WATCH")],
        key=lambda r: r.get("receivables") or 0,
        reverse=True,
    )[:8]
    if attention:
        st.dataframe(pd.DataFrame([
            {
                "Customer": fmt_customer_code(r.get("company_code")),
                "Health": classify_customer_health(r),
                "Receivable": fmt_inr(r.get("receivables")),
                "Pipeline": fmt_inr(r.get("open_pipeline")),
                "Collected": fmt_inr(r.get("collected")),
            }
            for r in attention
        ]), hide_index=True, use_container_width=True, height=200)

    _section("MAJOR CUSTOMERS — CROSS-BOARD")
    cross = intel.cross_board[:10]
    if cross:
        st.dataframe(pd.DataFrame([
            {
                "Customer": fmt_customer_code(r.get("company_code")),
                "Tier": r.get("tier"),
                "Billed": fmt_inr(r.get("billed")),
                "Collected": fmt_inr(r.get("collected")),
                "Receivable": fmt_inr(r.get("receivables")),
                "Pipeline": fmt_inr(r.get("open_pipeline")),
                "WOs": r.get("work_orders") or 0,
                "Health": r.get("health"),
            }
            for r in cross
        ]), hide_index=True, use_container_width=True, height=280)


def tab_operations(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    ops = metrics.operations
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    wo_total = metrics.data_quality.get("work_order_count") or intel.data_integrity.get("work_orders") or 0
    with c1:
        _kpi("TOTAL WOs", str(wo_total))
    with c2:
        _kpi("OPEN", str(ops.get("open_work_orders") or 0))
    with c3:
        _kpi("COMPLETED", str(ops.get("completed") or 0))
    with c4:
        _kpi("STUCK / DELAYED", str(ops.get("stuck") or 0))
    with c5:
        _kpi("NOT STARTED", str(ops.get("not_started") or 0))
    with c6:
        billing = sum(1 for r in intel.operations_risks if r.get("type") == "completed_unbilled")
        _kpi("BILLING ISSUES", str(billing))

    left, right = st.columns(2)
    with left:
        _section("EXECUTION STATUS")
        exec_status = ops.get("execution_status", [])
        if exec_status:
            df = pd.DataFrame([
                {"Status": (g.get("execution_status") or "?")[:20], "Count": g.get("count", 0)}
                for g in exec_status
            ])
            st.bar_chart(df.set_index("Status")["Count"], height=220)
    with right:
        _section("OPERATIONAL BOTTLENECKS")
        for risk in intel.operations_risks[:10]:
            st.markdown(
                f'<span class="fi-mono">{risk.get("type", "")}</span> '
                f'{fmt_customer_code(risk.get("company_code"))} {risk.get("detail", "")}',
                unsafe_allow_html=True,
            )


def tab_sectors(metrics: DashboardMetrics, intel: IntelligenceBundle) -> None:
    ranking = intel.sector_ranking
    if ranking:
        top = ranking[0]
        s1, s2, s3 = st.columns(3)
        with s1:
            _kpi("TOP SECTOR", top.get("sector", "—"), f"Pipeline {fmt_inr(top.get('pipeline'))}")
        with s2:
            highest_pipe = max(ranking, key=lambda s: s.get("pipeline") or 0)
            _kpi("HIGHEST PIPELINE", highest_pipe.get("sector", "—"), fmt_inr(highest_pipe.get("pipeline")))
        with s3:
            st.caption(intel.data_integrity.get("live_snapshot_note", ""))

    _section("SECTOR RANKING")
    if ranking:
        st.dataframe(pd.DataFrame([
            {
                "Rank": s.get("rank"),
                "Sector": s.get("sector"),
                "Pipeline": fmt_inr(s.get("pipeline")),
                "Contract": fmt_inr(s.get("contract_value")),
                "Work Orders": s.get("work_orders") or 0,
                "Momentum": s.get("momentum"),
            }
            for s in ranking
        ]), hide_index=True, use_container_width=True, height=260)

    left, right = st.columns(2)
    with left:
        _section("PIPELINE BY SECTOR")
        by_pipe = metrics.sectors.get("by_pipeline", [])[:8]
        if by_pipe:
            df = pd.DataFrame([
                {"Sector": (g.get("sector_normalized") or "?")[:16], "Pipeline": g.get("pipeline") or 0}
                for g in by_pipe
            ])
            st.bar_chart(df.set_index("Sector")["Pipeline"], height=200)
    with right:
        _section("BILLED BY SECTOR")
        by_contract = metrics.sectors.get("by_contract_value", [])[:8]
        if by_contract:
            df = pd.DataFrame([
                {"Sector": (g.get("sector_normalized") or "?")[:16], "Billed": g.get("contract_value") or 0}
                for g in by_contract
            ])
            st.bar_chart(df.set_index("Sector")["Billed"], height=200)


def tab_risks_opportunities(intel: IntelligenceBundle) -> None:
    left, right = st.columns(2)
    with left:
        _section("RISK RADAR")
        for cat_key, label in RISK_LABELS.items():
            items = intel.risks_by_category.get(cat_key, [])
            if not items:
                continue
            st.markdown(f'<div class="fi-cat-label">{label}</div>', unsafe_allow_html=True)
            for item in items[:3]:
                _insight_card(item)
    with right:
        _section("OPPORTUNITY RADAR")
        for cat_key, label in OPP_LABELS.items():
            items = intel.opportunities_by_category.get(cat_key, [])
            if not items:
                continue
            st.markdown(f'<div class="fi-cat-label">{label}</div>', unsafe_allow_html=True)
            for item in items[:2]:
                _insight_card(item)

    _section("FOUNDER ACTIONS")
    for action in intel.founder_actions[:5]:
        st.markdown(
            f'**{action.get("rank", 0):02d} — {action.get("category", "")}** — {action.get("detail", "")}'
        )


def tab_data_health(intel: IntelligenceBundle) -> None:
    dq = intel.data_integrity
    render_data_integrity_strip(dq, expanded=True)

    _section("DATA CONFIDENCE")
    conf = dq.get("confidence", "MEDIUM")
    st.markdown(f"Confidence: {_confidence_badge(conf)}", unsafe_allow_html=True)
    for reason in dq.get("confidence_reasons", []):
        st.markdown(f"- {reason}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi("RECORDS FETCHED", str(dq.get("records_analyzed", 0)))
    with c2:
        _kpi("WORK ORDERS", str(dq.get("work_orders", 0)))
    with c3:
        _kpi("DEALS", str(dq.get("deals", 0)))
    with c4:
        _kpi("UNMATCHED COMPANIES", str(dq.get("unmatched_companies", 0)))

    _section("DETAILED DIAGNOSTICS")
    diag = dq.get("diagnostics", [])
    if diag:
        st.dataframe(pd.DataFrame(diag), hide_index=True, use_container_width=True)

    detail_rows = [
        ("Missing deal dates", dq.get("missing_deal_dates")),
        ("Missing deal values", dq.get("missing_deal_values")),
        ("Missing company codes", dq.get("missing_company_codes")),
        ("Open deals no close date", dq.get("open_deals_no_close_date")),
        ("Sector mismatches", dq.get("sector_mismatches")),
        ("Cross-board matches", dq.get("cross_board_matches")),
    ]
    st.dataframe(
        pd.DataFrame([{"Issue": k, "Count": v} for k, v in detail_rows if v]),
        hide_index=True,
        use_container_width=True,
        height=220,
    )

    st.caption(dq.get("live_snapshot_note", ""))


def render_command_center(
    data: CachedMondayData,
    metrics: DashboardMetrics,
    data_service,
    *,
    data_ok: bool,
    debug_mode: bool = False,
    load_ms: float | None = None,
    chat_renderer=None,
) -> bool:
    """Tabbed founder intelligence UI. Returns True if refresh requested."""
    if not data_ok:
        st.warning("Some live data is temporarily unavailable. Please refresh.")

    if render_header(data, data_ok=data_ok):
        return True

    intel = build_intelligence(data, metrics)
    tab = st.radio(
        "Navigation",
        TABS,
        horizontal=True,
        label_visibility="collapsed",
        key="fi_nav",
    )

    if tab == "OVERVIEW":
        tab_overview(metrics, intel)
    elif tab == "REVENUE & CASH":
        tab_revenue(metrics, intel)
    elif tab == "PIPELINE":
        tab_pipeline(metrics, intel, data_service)
    elif tab == "CUSTOMERS":
        tab_customers(metrics, intel)
    elif tab == "OPERATIONS":
        tab_operations(metrics, intel)
    elif tab == "SECTORS":
        tab_sectors(metrics, intel)
    elif tab == "RISKS & OPPORTUNITIES":
        tab_risks_opportunities(intel)
    elif tab == "DATA HEALTH":
        tab_data_health(intel)
    elif tab == "ASK SKYLARK" and chat_renderer:
        chat_renderer()

    if debug_mode and load_ms is not None:
        with st.expander("Diagnostics", expanded=False):
            st.caption(f"Render: {load_ms:.0f}ms · Insights: {len(intel.insights)}")

    return False
