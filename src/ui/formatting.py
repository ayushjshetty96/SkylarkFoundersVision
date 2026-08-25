"""Executive number formatting for Skylark dashboard."""

from __future__ import annotations


def fmt_inr(value: float | None, *, compact: bool = True) -> str:
    """Format INR for executive display."""
    if value is None:
        return "—"
    if not compact:
        return f"₹{value:,.0f}"
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"₹{value / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        if abs_v < 10_000_000:
            return f"₹{value / 1_000_000:.2f}M"
        return f"₹{value / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"₹{value / 1_000:.0f}K"
    return f"₹{value:,.0f}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}%"


def fmt_customer_code(code: str | None, max_len: int = 14) -> str:
    if not code:
        return "—"
    code = str(code).replace("COMPANY", "Co.")
    if len(code) > max_len:
        return code[: max_len - 1] + "…"
    return code


def health_badge(status: str) -> str:
    colors = {
        "HEALTHY": "#3fb950",
        "WATCH": "#d29922",
        "AT RISK": "#f85149",
    }
    color = colors.get(status, "#8b949e")
    return f'<span style="color:{color};font-weight:600;font-size:0.8rem;">{status}</span>'
