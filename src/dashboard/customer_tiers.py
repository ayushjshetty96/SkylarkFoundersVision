"""Customer tier classification — not profitability."""

from __future__ import annotations

from typing import Any

from src.dashboard.health import classify_customer_health, load_dashboard_rules


def classify_customer_tier(row: dict[str, Any]) -> str:
    """
    STRATEGIC | GROWING | STABLE | WATCH | AT RISK
    Based on collected, pipeline, receivables, activity — no margin data.
    """
    rules = load_dashboard_rules().get("customer_tiers", {})
    strategic_collected = rules.get("strategic_collected_inr", 10_000_000)
    growing_pipeline = rules.get("growing_pipeline_inr", 5_000_000)

    collected = row.get("collected") or 0
    pipeline = row.get("open_pipeline") or 0
    receivables = row.get("receivables") or 0
    wos = row.get("work_orders") or 0
    health = classify_customer_health(row)

    if health == "AT RISK":
        return "AT RISK"
    if collected >= strategic_collected and (pipeline > 0 or wos >= 3):
        return "STRATEGIC"
    if pipeline >= growing_pipeline and collected > 0:
        return "GROWING"
    if health == "WATCH" or receivables > collected * 0.3:
        return "WATCH"
    if collected > 0:
        return "STABLE"
    return "WATCH"


def customer_concentration(rows: list[dict[str, Any]], *, top_n: int = 5) -> dict[str, Any]:
    """Share of collected revenue among top customers."""
    total_collected = sum(r.get("collected") or 0 for r in rows)
    if total_collected <= 0:
        return {"top_n": top_n, "share_pct": None, "top_customers": []}

    sorted_rows = sorted(rows, key=lambda r: r.get("collected") or 0, reverse=True)
    top = sorted_rows[:top_n]
    top_sum = sum(r.get("collected") or 0 for r in top)
    return {
        "top_n": top_n,
        "share_pct": round(top_sum / total_collected * 100, 1),
        "top_collected_inr": top_sum,
        "total_collected_inr": total_collected,
        "top_customers": [
            {"company_code": r.get("company_code"), "collected": r.get("collected")}
            for r in top
        ],
    }
