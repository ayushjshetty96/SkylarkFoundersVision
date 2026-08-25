"""Compact summary tools for the LLM agent — server-side Python only."""

from __future__ import annotations

from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.dashboard.health import classify_customer_health
from src.tools.customer_analysis import (
    _build_company_rows,
    _sort_rows,
    customer_analysis_tool,
)
from src.tools.join import join_by_company
from src.normalization.sectors import normalize_sector_query, sector_matches
from src.tools.aggregate import aggregate
from src.tools.pipeline_analysis import pipeline_analysis_tool
from src.utils.timer import timed


def _preload(data_service: DataService, work_orders=None, deals=None):
    if work_orders is None:
        work_orders = data_service.get_work_orders()
    if deals is None:
        deals = data_service.get_deals()
    return work_orders, deals


def customer_ranking_tool(
    data_service: DataService,
    *,
    limit: int = 10,
    sort_by: str = "collected",
    ranking: str | None = None,
    settings: Settings | None = None,
    work_orders=None,
    deals=None,
) -> dict[str, Any]:
    """Top customers by metric — compact JSON, max 15."""
    limit = max(1, min(int(limit), 15))
    ranking = (ranking or "").strip().lower()

    if ranking in ("best", "top"):
        return customer_analysis_tool(
            data_service, "good_customers", limit=limit,
            settings=settings, work_orders=work_orders, deals=deals,
        )
    if ranking in ("risk", "risky", "attention"):
        return customer_health_tool(
            data_service, limit=limit, settings=settings,
            work_orders=work_orders, deals=deals,
        )
    if ranking in ("receivables", "owe", "ar"):
        return customer_analysis_tool(
            data_service, "customer_receivables", limit=limit,
            settings=settings, work_orders=work_orders, deals=deals,
        )
    if ranking in ("pipeline",):
        return customer_analysis_tool(
            data_service, "customer_pipeline", limit=limit,
            settings=settings, work_orders=work_orders, deals=deals,
        )
    if ranking in ("overview", "customers", "talk", "about"):
        return customer_analysis_tool(
            data_service, "customer_overview", limit=limit,
            settings=settings, work_orders=work_orders, deals=deals,
        )
    if ranking in ("pipeline_and_work_orders", "compare", "major"):
        return customer_analysis_tool(
            data_service, "customer_overview", limit=limit,
            settings=settings, work_orders=work_orders, deals=deals,
        )

    return customer_analysis_tool(
        data_service,
        "top_customers",
        limit=limit,
        sort_by=sort_by,
        settings=settings,
        work_orders=work_orders,
        deals=deals,
    )


def customer_health_tool(
    data_service: DataService,
    *,
    limit: int = 10,
    settings: Settings | None = None,
    work_orders=None,
    deals=None,
) -> dict[str, Any]:
    work_orders, deals = _preload(data_service, work_orders, deals)
    join_result = join_by_company(deals, work_orders)
    rows = _build_company_rows(join_result)[:limit * 3]
    classified = []
    for row in rows:
        classified.append({
            **{k: row.get(k) for k in (
                "company_code", "collected", "billed", "receivables",
                "open_pipeline", "work_orders", "open_deals",
            )},
            "health": classify_customer_health(row),
        })
    by_risk = sorted(classified, key=lambda r: {"AT RISK": 0, "WATCH": 1, "HEALTHY": 2}[r["health"]])
    return {
        "customers": by_risk[:limit],
        "note": "Health classification from receivables/collection ratios — not profitability.",
    }


def sector_summary_tool(
    data_service: DataService,
    *,
    limit: int = 10,
    sector: str | None = None,
    period: str | None = None,
    focus: str | None = None,
    settings: Settings | None = None,
    work_orders=None,
    deals=None,
) -> dict[str, Any]:
    """Sector performance — optionally filtered by sector and/or period."""
    work_orders, deals = _preload(data_service, work_orders, deals)
    deal_dicts = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in deals]
    wo_dicts = [w.model_dump(mode="json") if hasattr(w, "model_dump") else w for w in work_orders]

    sector_query = normalize_sector_query(sector) if sector else None
    if sector_query:
        deal_dicts = [d for d in deal_dicts if sector_matches(d.get("sector_normalized") or d.get("sector"), sector_query)]
        wo_dicts = [w for w in wo_dicts if sector_matches(w.get("sector_normalized") or w.get("sector"), sector_query)]

    open_deals = [d for d in deal_dicts if d.get("deal_status") == "Open"]
    if period:
        from src.normalization.date_ranges import resolve_period
        from src.tools.pipeline_analysis import filter_open_deals

        date_range = resolve_period(period)
        if date_range:
            open_deals, _ = filter_open_deals(deal_dicts, sector=None, period=date_range)

    weights = {
        "High": (settings or get_settings()).prob_weight_high,
        "Medium": (settings or get_settings()).prob_weight_medium,
        "Low": (settings or get_settings()).prob_weight_low,
    }
    from src.tools.aggregate import weighted_pipeline_sum

    pipeline = weighted_pipeline_sum(open_deals, weights=weights)
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

    collected = aggregate(
        wo_dicts,
        metrics=[{"name": "collected", "field": "collected_amount_incl_gst", "op": "sum"}],
    )

    result: dict[str, Any] = {
        "sector_filter": sector_query,
        "period": period,
        "focus": focus,
        "open_pipeline_inr": pipeline.get("raw_pipeline_value"),
        "weighted_pipeline_inr": pipeline.get("weighted_pipeline_value"),
        "open_deal_count": pipeline.get("open_deal_count"),
        "collected_inr": collected.metrics.get("collected"),
        "by_contract_value": sorted(
            sector_contract.groups, key=lambda g: g.get("contract_value") or 0, reverse=True,
        )[:limit],
        "by_pipeline": sorted(
            sector_pipeline.groups, key=lambda g: g.get("pipeline") or 0, reverse=True,
        )[:limit],
        "by_work_orders": sorted(
            sector_wo.groups, key=lambda g: g.get("wo_count") or 0, reverse=True,
        )[:limit],
        "currency": "INR",
        "record_count_deals": len(deal_dicts),
        "record_count_work_orders": len(wo_dicts),
    }
    if sector_query:
        result["note"] = f"Filtered to sector: {sector_query}"
    return result


def pipeline_summary_tool(
    data_service: DataService,
    settings: Settings | None = None,
    work_orders=None,
    deals=None,
    *,
    sector: str | None = None,
    period: str | None = None,
) -> dict[str, Any]:
    """Compact pipeline summary — supports optional sector/period filters."""
    if sector or period:
        return pipeline_analysis_tool(
            data_service,
            sector=sector,
            period=period,
            settings=settings,
            work_orders=work_orders,
            deals=deals,
        )

    work_orders, deals = _preload(data_service, work_orders, deals)
    preload = {"work_orders": work_orders, "deals": deals}
    with timed("pipeline_summary"):
        snapshot = generate_leadership_snapshot(
            data_service, settings, **preload,
        )
    sections = snapshot.get("sections", {})
    pipeline = sections.get("pipeline_headline", {})
    stages = sections.get("pipeline_by_stage", {})
    return {
        "open_deal_count": pipeline.get("open_deal_count"),
        "open_pipeline_inr": pipeline.get("raw_pipeline_value_inr"),
        "weighted_pipeline_inr": pipeline.get("weighted_pipeline_value_inr"),
        "stale_open_deals": sections.get("cross_board_risks", {}).get("stale_open_deals_count"),
        "stages": (stages.get("groups") if isinstance(stages, dict) else [])[:10],
    }


def operations_summary_tool(
    data_service: DataService,
    settings: Settings | None = None,
    work_orders=None,
    deals=None,
) -> dict[str, Any]:
    work_orders, deals = _preload(data_service, work_orders, deals)
    preload = {"work_orders": work_orders, "deals": deals}
    snapshot = generate_leadership_snapshot(data_service, settings, **preload)
    ops = snapshot.get("sections", {}).get("operations", {})
    return {
        "not_started": ops.get("not_started"),
        "ongoing": ops.get("ongoing"),
        "execution_status": ops.get("execution_status", [])[:10],
        "billing_status": ops.get("billing_status", [])[:10],
    }
