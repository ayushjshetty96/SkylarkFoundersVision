"""Executive fallback formatting when tool rounds are exhausted."""

from __future__ import annotations

from typing import Any


def format_executive_fallback(compact_results: list[dict[str, Any]]) -> str:
    """Turn compact tool output into a founder-friendly partial answer."""
    if not compact_results:
        return (
            "I couldn't complete the full analysis within the response limit. "
            "Please try a more specific question."
        )

    last = compact_results[-1]
    lines = [
        "I couldn't complete the full analysis within the response limit. "
        "Here's the information I could verify:",
        "",
    ]

    # Revenue summary
    if last.get("metric") == "revenue_summary" or last.get("metrics"):
        metrics = last.get("metrics") or {}
        billed = _nested_val(metrics, "billed_revenue")
        collected = _nested_val(metrics, "collected_revenue")
        receivables = _nested_val(metrics, "receivables")
        if billed is not None:
            lines.append(f"- Billed revenue: {_fmt_inr(billed)}")
        if collected is not None:
            lines.append(f"- Collected: {_fmt_inr(collected)}")
        if receivables is not None:
            lines.append(f"- Receivables: {_fmt_inr(receivables)}")
        lines.append("- Revenue here means billed revenue; these measures are not summed together.")

    elif last.get("analysis") == "pipeline" or last.get("pipeline_inr") is not None:
        if last.get("sector"):
            lines.append(f"- Sector: {last['sector']}")
        if last.get("period"):
            lines.append(f"- Period: {last['period']}")
        if last.get("open_deal_count") is not None:
            lines.append(f"- Open deals: {last['open_deal_count']}")
        if last.get("pipeline_inr") is not None:
            lines.append(f"- Pipeline: {_fmt_inr(last['pipeline_inr'])}")
        if last.get("weighted_pipeline_inr") is not None:
            lines.append(f"- Weighted pipeline: {_fmt_inr(last['weighted_pipeline_inr'])}")

    elif last.get("open_pipeline_inr") is not None:
        lines.append(f"- Open pipeline: {_fmt_inr(last['open_pipeline_inr'])}")
        if last.get("open_deal_count") is not None:
            lines.append(f"- Open deals: {last['open_deal_count']}")

    elif last.get("value") is not None and last.get("metric"):
        lines.append(f"- {last['metric'].replace('_', ' ').title()}: {_fmt_val(last)}")

    elif last.get("customers"):
        lines.append("- Key customers identified:")
        for c in last["customers"][:5]:
            code = c.get("company_code", "—")
            recv = c.get("receivables")
            coll = c.get("collected")
            if recv is not None:
                lines.append(f"  • {code}: receivables {_fmt_inr(recv)}")
            elif coll is not None:
                lines.append(f"  • {code}: collected {_fmt_inr(coll)}")
            else:
                lines.append(f"  • {code}")

    elif last.get("summary"):
        summary = last["summary"]
        if summary.get("top_by_collected"):
            lines.append("- Top customers by collected revenue identified.")
        if summary.get("top_by_receivables"):
            lines.append("- Customers with highest receivables identified.")
        if summary.get("major_customers_cross_board"):
            lines.append("- Cross-board customer comparison available for major accounts.")

    elif last.get("sections"):
        lines.append("- Executive snapshot sections retrieved (pipeline, cash, operations, risks).")

    else:
        lines.append("- Partial analysis completed. Please ask a narrower follow-up.")

    caveats = last.get("data_quality_caveats") or []
    if caveats:
        lines.append("")
        lines.append("Note: " + caveats[0])

    lines.append("")
    lines.append("Ask a follow-up for more detail on one area.")
    return "\n".join(lines)


def _nested_val(metrics: dict, key: str) -> float | None:
    entry = metrics.get(key, {})
    if isinstance(entry, dict):
        return entry.get("value")
    return None


def _fmt_inr(value: float | None) -> str:
    if value is None:
        return "—"
    abs_v = abs(value)
    if abs_v >= 1_000_000:
        return f"₹{value / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"₹{value / 1_000:.0f}K"
    return f"₹{value:,.0f}"


def _fmt_val(result: dict[str, Any]) -> str:
    value = result.get("value")
    if result.get("currency") == "INR" and isinstance(value, (int, float)):
        return _fmt_inr(float(value))
    return str(value)
