"""JARVIS alert center — thresholds from config/dashboard_rules.json."""

from __future__ import annotations

from typing import Any

from src.dashboard.health import load_dashboard_rules


def generate_alerts(metrics: Any) -> list[dict[str, Any]]:
    rules = load_dashboard_rules().get("alerts", {})
    alerts: list[dict[str, Any]] = []

    rev = metrics.revenue
    pipe = metrics.pipeline
    ops = metrics.operations
    dq = metrics.data_quality

    priority_ar = rev.get("priority_ar_inr")
    if priority_ar is None:
        priority_ar = 0

    stale = pipe.get("stale_open_deals") or 0
    if stale >= rules.get("stale_open_deals", 10):
        alerts.append({
            "category": "HIGH PRIORITY",
            "message": f"{stale} stale open deal{'s' if stale != 1 else ''}",
        })

    ar = rev.get("receivables") or 0
    if ar >= rules.get("priority_ar_inr", 1_000_000):
        alerts.append({
            "category": "HIGH PRIORITY",
            "message": f"High receivables detected: ₹{ar:,.0f}",
        })

    deal_only = dq.get("deal_only_company_count") or 0
    if deal_only >= rules.get("deal_only_companies", 50):
        alerts.append({
            "category": "WATCH",
            "message": f"{deal_only} deal-only companies have no matching work order",
        })

    missing = dq.get("missing_deal_values") or 0
    if missing >= rules.get("missing_deal_values", 20):
        alerts.append({
            "category": "DATA QUALITY",
            "message": f"{missing} deals missing financial values",
        })

    stuck = ops.get("stuck") or 0
    if stuck >= rules.get("stuck_work_orders", 1):
        alerts.append({
            "category": "OPERATIONAL",
            "message": f"{stuck} work order{'s' if stuck != 1 else ''} currently stuck/paused",
        })

    not_started = ops.get("not_started") or 0
    if not_started >= rules.get("not_started_work_orders", 5):
        alerts.append({
            "category": "OPERATIONAL",
            "message": f"{not_started} work orders not started",
        })

    sector_mm = dq.get("sector_mismatch_companies") or 0
    if sector_mm >= rules.get("sector_mismatch_companies", 1):
        alerts.append({
            "category": "DATA QUALITY",
            "message": f"{sector_mm} cross-board sector mismatches",
        })

    return alerts
