"""Deterministic dashboard metrics — no Groq."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.settings import Settings, get_settings
from src.dashboard.data import CachedMondayData
from src.models.deal import Deal
from src.models.work_order import WorkOrder
from src.tools.aggregate import aggregate, weighted_pipeline_sum
from src.tools.business_metric import business_metric_tool
from src.tools.customer_analysis import build_customer_rankings_bundle, _build_company_rows, _sort_rows
from src.tools.join import join_by_company
from src.utils.timer import timed


@dataclass
class DashboardMetrics:
    revenue: dict[str, Any] = field(default_factory=dict)
    pipeline: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, Any] = field(default_factory=dict)
    customers: dict[str, Any] = field(default_factory=dict)
    sectors: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    join_summary: dict[str, Any] = field(default_factory=dict)


def _safe_ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def calculate_revenue_metrics(
    data_service,
    data: CachedMondayData,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    return business_metric_tool(
        data_service,
        "total_revenue",
        settings=settings,
        work_orders=data.work_orders,
        deals=data.deals,
    )


def calculate_all_metrics(
    data_service,
    data: CachedMondayData,
    settings: Settings | None = None,
    *,
    top_n: int = 10,
) -> DashboardMetrics:
    settings = settings or get_settings()
    preload = {"work_orders": data.work_orders, "deals": data.deals}

    with timed("Dashboard revenue metrics"):
        revenue = business_metric_tool(
            data_service, "total_revenue", settings=settings, **preload,
        )

    wo_dicts = [w.model_dump(mode="json") for w in data.work_orders]
    deal_dicts = [d.model_dump(mode="json") for d in data.deals]
    open_deals = [d for d in deal_dicts if d.get("deal_status") == "Open"]
    won_deals = [d for d in deal_dicts if d.get("deal_status") == "Won"]
    lost_deals = [d for d in deal_dicts if d.get("deal_status") == "Lost"]

    weights = {
        "High": settings.prob_weight_high,
        "Medium": settings.prob_weight_medium,
        "Low": settings.prob_weight_low,
    }

    with timed("Dashboard pipeline metrics"):
        pipeline_sum = weighted_pipeline_sum(deal_dicts, weights=weights)
        stage_agg = aggregate(
            open_deals,
            group_by=["deal_stage"],
            metrics=[
                {"name": "deal_count", "field": "*", "op": "count"},
                {"name": "pipeline_value", "field": "deal_value", "op": "sum"},
            ],
        )
        avg_deal = aggregate(
            open_deals,
            metrics=[{"name": "avg_value", "field": "deal_value", "op": "avg"}],
        )

    with timed("Dashboard operations metrics"):
        exec_agg = aggregate(
            wo_dicts,
            group_by=["execution_status"],
            metrics=[{"name": "count", "field": "*", "op": "count"}],
        )
        billing_agg = aggregate(
            wo_dicts,
            group_by=["billing_status"],
            metrics=[{"name": "count", "field": "*", "op": "count"}],
        )
        priority_ar_agg = aggregate(
            wo_dicts,
            metrics=[{"name": "priority_ar", "field": "amount_receivable", "op": "sum"}],
            filters={"ar_priority": True},
        )

    with timed("Join"):
        join_result = join_by_company(data.deals, data.work_orders)

    with timed("Dashboard customer metrics"):
        rankings = build_customer_rankings_bundle(
            data_service, top_n=top_n, settings=settings, **preload,
        )
        company_rows = _build_company_rows(join_result)

    with timed("Dashboard sector metrics"):
        sector_contract = aggregate(
            wo_dicts,
            group_by=["sector_normalized"],
            metrics=[{"name": "contract_value", "field": "contract_value_incl_gst", "op": "sum"}],
        )
        sector_pipeline = aggregate(
            open_deals,
            group_by=["sector_normalized"],
            metrics=[{"name": "pipeline", "field": "deal_value", "op": "sum"}],
        )
        sector_wo = aggregate(
            wo_dicts,
            group_by=["sector_normalized"],
            metrics=[{"name": "wo_count", "field": "*", "op": "count"}],
        )

    metrics_map = revenue.get("metrics", {})
    contract = _metric_val(metrics_map, "contract_value")
    billed = _metric_val(metrics_map, "billed_revenue")
    collected = _metric_val(metrics_map, "collected_revenue")
    receivables = _metric_val(metrics_map, "receivables")

    stale = sum(1 for d in open_deals if d.get("is_stale_close_date"))
    missing_values = sum(1 for d in deal_dicts if d.get("deal_value") is None)
    parse_failures = sum(
        1 for w in data.work_orders if any("parse_failed" in fw for fw in w.field_warnings)
    )
    sector_mismatches = sum(
        1 for c in join_result.companies
        if any("sector mismatch" in w for w in c.match_warnings)
    )

    exec_groups = exec_agg.groups
    not_started = sum(g.get("count", 0) for g in exec_groups if g.get("execution_status") == "Not Started")
    ongoing = sum(g.get("count", 0) for g in exec_groups if g.get("execution_status") == "Ongoing")
    completed = sum(g.get("count", 0) for g in exec_groups if g.get("execution_status") == "Completed")
    stuck = sum(
        g.get("count", 0) for g in exec_groups
        if g.get("execution_status") and (
            "stuck" in str(g.get("execution_status")).lower()
            or "paused" in str(g.get("execution_status")).lower()
        )
    )

    return DashboardMetrics(
        revenue={
            "summary": revenue,
            "contract_value": contract,
            "billed_revenue": billed,
            "collected_revenue": collected,
            "receivables": receivables,
            "priority_ar_inr": priority_ar_agg.metrics.get("priority_ar"),
            "billing_rate": _safe_ratio(billed, contract),
            "collection_rate": _safe_ratio(collected, billed),
        },
        pipeline={
            "open_pipeline": pipeline_sum["raw_pipeline_value"],
            "weighted_pipeline": pipeline_sum["weighted_pipeline_value"],
            "open_deal_count": pipeline_sum["open_deal_count"],
            "won_deal_count": len(won_deals),
            "lost_deal_count": len(lost_deals),
            "stale_open_deals": stale,
            "avg_deal_value": avg_deal.metrics.get("avg_value"),
            "stages": stage_agg.groups,
            "missing_deal_value_count": pipeline_sum["missing_value_count"],
        },
        operations={
            "execution_status": exec_groups,
            "billing_status": billing_agg.groups,
            "not_started": not_started,
            "ongoing": ongoing,
            "completed": completed,
            "stuck": stuck,
            "open_work_orders": not_started + ongoing,
        },
        customers={
            "rankings": rankings,
            "rows": company_rows,
            "top_collected": rankings.get("collected", {}).get("customers", []),
        },
        sectors={
            "by_contract_value": sorted(
                sector_contract.groups, key=lambda g: g.get("contract_value") or 0, reverse=True,
            )[:10],
            "by_pipeline": sorted(
                sector_pipeline.groups, key=lambda g: g.get("pipeline") or 0, reverse=True,
            )[:10],
            "by_work_orders": sorted(
                sector_wo.groups, key=lambda g: g.get("wo_count") or 0, reverse=True,
            )[:10],
        },
        data_quality={
            "work_order_count": data.work_order_count,
            "deal_count": data.deal_count,
            "missing_deal_values": missing_values,
            "numeric_parse_failures": parse_failures,
            "sector_mismatch_companies": sector_mismatches,
            "wo_only_companies": join_result.unmatched.get("wo_only", []),
            "deal_only_company_count": join_result.unmatched.get("deal_only_count", 0),
            "matched_companies": join_result.match_summary.normalized_exact,
            "match_rate": _safe_ratio(
                join_result.match_summary.normalized_exact,
                join_result.match_summary.normalized_exact
                + join_result.match_summary.unmatched_wo_only
                + join_result.match_summary.unmatched_deal_only,
            ),
        },
        join_summary=join_result.match_summary.model_dump(mode="json"),
    )


def _metric_val(metrics: dict, key: str) -> float | None:
    entry = metrics.get(key, {})
    if isinstance(entry, dict):
        return entry.get("value")
    return None
