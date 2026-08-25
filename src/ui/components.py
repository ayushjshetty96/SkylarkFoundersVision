"""Streamlit UI components."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_tool_trace(tool_trace: list[dict[str, Any]]) -> None:
    if not tool_trace:
        return
    with st.expander("Data & tools used", expanded=False):
        for entry in tool_trace:
            st.markdown(f"**{entry['tool']}**")
            if entry.get("args"):
                st.json(entry["args"])
            if entry.get("result_summary"):
                st.json(entry["result_summary"])


def render_leadership_snapshot(snapshot: dict[str, Any]) -> None:
    sections = snapshot.get("sections", {})

    st.subheader("Executive Snapshot")
    st.caption(f"As of {snapshot.get('as_of', 'N/A')} | Source: {snapshot.get('source', 'monday_api')}")

    pipeline = sections.get("pipeline_headline", {})
    col1, col2, col3 = st.columns(3)
    col1.metric("Open Deals", pipeline.get("open_deal_count", "N/A"))
    raw_val = pipeline.get("raw_pipeline_value_inr")
    col2.metric("Open Pipeline (INR)", f"₹{raw_val:,.0f}" if raw_val else "N/A")
    weighted = pipeline.get("weighted_pipeline_value_inr")
    col3.metric("Weighted Pipeline (INR)", f"₹{weighted:,.0f}" if weighted else "N/A")

    if pipeline.get("missing_deal_value_count"):
        st.warning(
            f"{pipeline['missing_deal_value_count']} deals excluded from pipeline sums due to missing values."
        )

    cash = sections.get("cash_collection", {})
    st.markdown("### Cash Collection")
    st.metric("Total AR (INR)", f"₹{cash.get('total_ar_inr', 0):,.0f}")
    st.metric("Priority AR (INR)", f"₹{cash.get('priority_ar_inr', 0):,.0f}")

    ops = sections.get("operations", {})
    st.markdown("### Operations")
    st.write(f"Not Started: {ops.get('not_started', 0)} | Ongoing: {ops.get('ongoing', 0)}")

    risks = sections.get("cross_board_risks", {})
    st.markdown("### Cross-Board Risks")
    st.write(f"Stale open deals: {risks.get('stale_open_deals_count', 0)}")
    risk_companies = risks.get("companies_with_pipeline_and_ar", [])
    if risk_companies:
        st.dataframe(risk_companies)

    dq = sections.get("data_quality", {})
    st.markdown("### Data Quality")
    st.json(dq)
