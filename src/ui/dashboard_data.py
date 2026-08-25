"""Deterministic dashboard data bundle — single fetch via existing tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.tools.business_metric import business_metric_tool
from src.tools.customer_analysis import build_customer_rankings_bundle
from src.tools.leadership import generate_leadership_snapshot


@dataclass
class DashboardBundle:
    """Pre-computed dashboard payload from deterministic tools."""

    loaded_at: str
    leadership: dict[str, Any]
    revenue: dict[str, Any]
    customers_collected: dict[str, Any]
    customers_billed: dict[str, Any]
    customers_receivables: dict[str, Any]
    customers_contract: dict[str, Any]
    customers_attention: dict[str, Any]
    customer_overview: dict[str, Any]
    risks: list[dict[str, Any]] = field(default_factory=list)
    work_order_count: int = 0
    deal_count: int = 0

    @property
    def financial(self) -> dict[str, float | None]:
        metrics = self.revenue.get("metrics", {})
        contract = _metric_value(metrics, "contract_value")
        billed = _metric_value(metrics, "billed_revenue")
        collected = _metric_value(metrics, "collected_revenue")
        receivables = _metric_value(metrics, "receivables")
        return {
            "contract_value": contract,
            "billed_revenue": billed,
            "collected_revenue": collected,
            "receivables": receivables,
            "billing_realization": _safe_ratio(billed, contract),
            "collection_realization": _safe_ratio(collected, billed),
        }

    @property
    def pipeline(self) -> dict[str, Any]:
        headline = self.leadership.get("sections", {}).get("pipeline_headline", {})
        stage_data = self.leadership.get("sections", {}).get("pipeline_by_stage", {})
        return {
            "open_pipeline": headline.get("raw_pipeline_value_inr"),
            "weighted_pipeline": headline.get("weighted_pipeline_value_inr"),
            "open_deal_count": headline.get("open_deal_count"),
            "stale_open_deals": self.leadership.get("sections", {}).get(
                "cross_board_risks", {}
            ).get("stale_open_deals_count", 0),
            "stages": stage_data.get("groups", []) if isinstance(stage_data, dict) else [],
            "missing_deal_value_count": headline.get("missing_deal_value_count", 0),
        }

    @property
    def operations(self) -> dict[str, Any]:
        ops = self.leadership.get("sections", {}).get("operations", {})
        return {
            "execution_status": ops.get("execution_status", []),
            "not_started": ops.get("not_started", 0),
            "ongoing": ops.get("ongoing", 0),
            "billing_status": ops.get("billing_status", []),
        }


def _metric_value(metrics: dict[str, Any], key: str) -> float | None:
    entry = metrics.get(key, {})
    if isinstance(entry, dict):
        return entry.get("value")
    return None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def build_dashboard_bundle(
    data_service: DataService,
    settings: Settings | None = None,
    *,
    top_n: int = 5,
) -> DashboardBundle:
    """Load all dashboard data via existing deterministic tools (cached by caller)."""
    settings = settings or get_settings()
    loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Single Monday fetch for entire dashboard
    work_orders = data_service.get_work_orders()
    deals = data_service.get_deals()
    preload = {"work_orders": work_orders, "deals": deals}

    leadership = generate_leadership_snapshot(data_service, settings, **preload)
    revenue = business_metric_tool(data_service, "total_revenue", settings=settings, **preload)

    rankings = build_customer_rankings_bundle(
        data_service, top_n=top_n, settings=settings, **preload,
    )

    dq = leadership.get("sections", {}).get("data_quality", {})
    risks = build_risk_radar(leadership, revenue)

    return DashboardBundle(
        loaded_at=loaded_at,
        leadership=leadership,
        revenue=revenue,
        customers_collected=rankings["collected"],
        customers_billed=rankings["billed"],
        customers_receivables=rankings["receivables"],
        customers_contract=rankings["contract"],
        customers_attention=rankings["attention"],
        customer_overview=rankings["overview"],
        risks=risks,
        work_order_count=dq.get("work_order_count", 0),
        deal_count=dq.get("deal_count", 0),
    )


def build_risk_radar(
    leadership: dict[str, Any],
    revenue: dict[str, Any],
) -> list[dict[str, Any]]:
    """Derive risk items from leadership snapshot — no invented thresholds."""
    sections = leadership.get("sections", {})
    pipeline = sections.get("pipeline_headline", {})
    cash = sections.get("cash_collection", {})
    ops = sections.get("operations", {})
    risks_section = sections.get("cross_board_risks", {})
    dq = sections.get("data_quality", {})

    items: list[dict[str, Any]] = []

    stale = risks_section.get("stale_open_deals_count", 0)
    if stale:
        items.append({
            "severity": "HIGH",
            "label": f"{stale} stale open deal{'s' if stale != 1 else ''}",
            "explanation": "Open deals with stale close dates require review.",
        })

    priority_ar = cash.get("priority_ar_inr")
    if priority_ar and priority_ar > 0:
        items.append({
            "severity": "HIGH",
            "label": f"₹{priority_ar:,.0f} priority receivables",
            "explanation": "Work orders flagged as priority AR.",
        })

    total_ar = cash.get("total_ar_inr")
    if total_ar and total_ar > 0:
        items.append({
            "severity": "WATCH",
            "label": f"₹{total_ar:,.0f} total outstanding receivables",
            "explanation": "Aggregate AR across work orders.",
        })

    billing_groups = ops.get("billing_status", [])
    billing_blockers = sum(
        g.get("count", 0) for g in billing_groups
        if g.get("billing_status") and "update" in str(g.get("billing_status")).lower()
    )
    if not billing_blockers:
        billing_blockers = sum(
            g.get("count", 0) for g in billing_groups
            if g.get("billing_status") and str(g.get("billing_status")).lower() not in (
                "billed", "completed", "done", "paid", "none", "",
            )
        )
    if billing_blockers:
        items.append({
            "severity": "WATCH",
            "label": f"{billing_blockers} billing status item{'s' if billing_blockers != 1 else ''} need attention",
            "explanation": "Non-completed billing statuses on work orders.",
        })

    not_started = ops.get("not_started", 0)
    if not_started:
        items.append({
            "severity": "WATCH",
            "label": f"{not_started} work order{'s' if not_started != 1 else ''} not started",
            "explanation": "Execution status = Not Started.",
        })

    paused = sum(
        g.get("count", 0) for g in ops.get("execution_status", [])
        if g.get("execution_status") and "stuck" in str(g.get("execution_status")).lower()
        or g.get("execution_status") and "paused" in str(g.get("execution_status")).lower()
    )
    if paused:
        items.append({
            "severity": "HIGH",
            "label": f"{paused} paused/stuck work order{'s' if paused != 1 else ''}",
            "explanation": "Execution blocked or paused.",
        })

    missing_values = dq.get("missing_deal_values", 0)
    if missing_values:
        items.append({
            "severity": "WATCH",
            "label": f"{missing_values} deal{'s' if missing_values != 1 else ''} missing values",
            "explanation": "Deal value field is null.",
        })

    parse_failures = dq.get("numeric_parse_failures", 0)
    if parse_failures:
        items.append({
            "severity": "WATCH",
            "label": f"{parse_failures} numeric parse failure{'s' if parse_failures != 1 else ''}",
            "explanation": "Fields failed numeric normalization.",
        })

    sector_mismatch = dq.get("sector_mismatch_companies", 0)
    if sector_mismatch:
        items.append({
            "severity": "WATCH",
            "label": f"{sector_mismatch} sector mismatch{'es' if sector_mismatch != 1 else ''}",
            "explanation": "Cross-board sector labels differ for matched companies.",
        })

    deal_only = dq.get("deal_only_company_count", 0)
    if deal_only:
        items.append({
            "severity": "INFO",
            "label": f"{deal_only} deal-only compan{'ies' if deal_only != 1 else 'y'}",
            "explanation": "Companies in Deals without matching Work Orders.",
        })

    cross_risks = risks_section.get("companies_with_pipeline_and_ar", [])
    if cross_risks:
        items.append({
            "severity": "HIGH",
            "label": f"{len(cross_risks)} companies with pipeline + AR",
            "explanation": "Simultaneous open pipeline and outstanding receivables.",
        })

    return items


def compact_briefing_facts(bundle: DashboardBundle) -> dict[str, Any]:
    """Compact facts for Groq executive briefing — no raw records."""
    fin = bundle.financial
    pipe = bundle.pipeline
    ops = bundle.operations
    return {
        "as_of": bundle.leadership.get("as_of"),
        "contract_value_inr": fin.get("contract_value"),
        "billed_revenue_inr": fin.get("billed_revenue"),
        "collected_revenue_inr": fin.get("collected_revenue"),
        "receivables_inr": fin.get("receivables"),
        "billing_realization_pct": (
            round(fin["billing_realization"] * 100, 1)
            if fin.get("billing_realization") is not None else None
        ),
        "collection_realization_pct": (
            round(fin["collection_realization"] * 100, 1)
            if fin.get("collection_realization") is not None else None
        ),
        "open_pipeline_inr": pipe.get("open_pipeline"),
        "weighted_pipeline_inr": pipe.get("weighted_pipeline"),
        "open_deal_count": pipe.get("open_deal_count"),
        "stale_open_deals": pipe.get("stale_open_deals"),
        "not_started_work_orders": ops.get("not_started"),
        "ongoing_work_orders": ops.get("ongoing"),
        "priority_ar_inr": bundle.leadership.get("sections", {}).get(
            "cash_collection", {}
        ).get("priority_ar_inr"),
        "top_risks": [r["label"] for r in bundle.risks[:5]],
        "work_order_count": bundle.work_order_count,
        "deal_count": bundle.deal_count,
    }
