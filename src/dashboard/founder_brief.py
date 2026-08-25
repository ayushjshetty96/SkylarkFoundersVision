"""Deterministic founder briefing — no LLM required."""

from __future__ import annotations

from typing import Any

from src.dashboard.intelligence_engine import IntelligenceBundle, _fmt_inr_short
from src.dashboard.metrics import DashboardMetrics
from src.ui.formatting import fmt_customer_code


def generate_founder_brief(metrics: DashboardMetrics, intel: IntelligenceBundle) -> dict[str, Any]:
    """One-click founder brief from live snapshot data."""
    rev = metrics.revenue
    pipe = metrics.pipeline
    dq = intel.data_integrity
    rows = intel.cross_board

    top_customer = rows[0] if rows else None
    at_risk = [r for r in rows if r.get("health") == "AT RISK"][:3]
    top_sector = intel.sector_ranking[0] if intel.sector_ranking else None

    cash_risks = [r for r in intel.risks if r.get("risk_type") == "CASH_RISK"]
    cust_risks = [r for r in intel.risks if r.get("risk_type") == "CUSTOMER_RISK"]
    pipe_risks = [r for r in intel.risks if r.get("risk_type") == "PIPELINE_RISK"]
    ops_risks = [r for r in intel.risks if r.get("risk_type") == "OPERATIONAL_RISK"]
    data_risks = [r for r in intel.risks if r.get("risk_type") == "DATA_RISK"]

    all_risks = cash_risks + cust_risks + pipe_risks + ops_risks + data_risks
    top_risks = all_risks[:3] or intel.risks[:3]
    top_opps = intel.opportunities[:3]

    return {
        "title": "FOUNDER BRIEF",
        "snapshot_note": dq.get("live_snapshot_note"),
        "data_confidence": dq.get("confidence"),
        "financial": {
            "billed_revenue": _fmt_inr_short(rev.get("billed_revenue")),
            "collected": _fmt_inr_short(rev.get("collected_revenue")),
            "receivables": _fmt_inr_short(rev.get("receivables")),
            "collection_rate_pct": round((rev.get("collection_rate") or 0) * 100),
            "open_pipeline": _fmt_inr_short(pipe.get("open_pipeline")),
            "open_deals": pipe.get("open_deal_count"),
        },
        "customers": {
            "top_customer": fmt_customer_code(top_customer.get("company_code")) if top_customer else None,
            "top_collected": _fmt_inr_short(top_customer.get("collected")) if top_customer else None,
            "at_risk": [
                {
                    "customer": fmt_customer_code(r.get("company_code")),
                    "receivables": _fmt_inr_short(r.get("receivables")),
                }
                for r in at_risk
            ],
        },
        "operations": {
            "stuck_work_orders": metrics.operations.get("stuck") or 0,
            "not_started": metrics.operations.get("not_started") or 0,
            "bottleneck": intel.operations_risks[0].get("detail") if intel.operations_risks else None,
        },
        "sectors": {
            "top_sector": top_sector.get("sector") if top_sector else None,
            "top_pipeline": _fmt_inr_short(top_sector.get("pipeline")) if top_sector else None,
        },
        "risks": [
            {"title": r.get("title"), "metric": r.get("metric"), "action": r.get("action")}
            for r in top_risks
        ],
        "opportunities": [
            {"title": o.get("title"), "metric": o.get("metric"), "action": o.get("action")}
            for o in top_opps
        ],
        "founder_actions": intel.founder_actions[:5],
        "caveats": list(dq.get("caveats", {}).values())[:3],
    }
