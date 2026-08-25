"""Deterministic leadership snapshot from live Monday data."""

from __future__ import annotations

from datetime import date
from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.models.records import Deal, WorkOrder
from src.tools.aggregate import aggregate, weighted_pipeline_sum
from src.tools.join import join_by_company


def generate_leadership_snapshot(
    data_service: DataService,
    settings: Settings | None = None,
    *,
    work_orders: list[WorkOrder] | None = None,
    deals: list[Deal] | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    as_of = date.today().isoformat()

    if work_orders is None:
        work_orders = data_service.get_work_orders()
    if deals is None:
        deals = data_service.get_deals()

    wo_dicts = [w.model_dump(mode="json") for w in work_orders]
    deal_dicts = [d.model_dump(mode="json") for d in deals]
    open_deals = [d for d in deal_dicts if d.get("deal_status") == "Open"]

    weights = {
        "High": settings.prob_weight_high,
        "Medium": settings.prob_weight_medium,
        "Low": settings.prob_weight_low,
    }
    pipeline = weighted_pipeline_sum(deal_dicts, weights=weights)

    pipeline_by_stage = aggregate(
        open_deals,
        group_by=["deal_stage"],
        metrics=[
            {"name": "deal_count", "field": "*", "op": "count"},
            {"name": "pipeline_value", "field": "deal_value", "op": "sum"},
        ],
    )

    ar_agg = aggregate(
        wo_dicts,
        metrics=[
            {"name": "total_ar", "field": "amount_receivable", "op": "sum"},
            {"name": "wo_count", "field": "*", "op": "count"},
        ],
        filters={},
    )

    priority_ar = aggregate(
        wo_dicts,
        metrics=[{"name": "priority_ar", "field": "amount_receivable", "op": "sum"}],
        filters={"ar_priority": True},
    )

    top_ar = aggregate(
        wo_dicts,
        group_by=["company_code"],
        metrics=[
            {"name": "ar", "field": "amount_receivable", "op": "sum"},
            {"name": "wo_count", "field": "*", "op": "count"},
        ],
    )
    top_ar_groups = sorted(
        [g for g in top_ar.groups if g.get("ar")],
        key=lambda x: x.get("ar", 0),
        reverse=True,
    )[:5]

    execution_breakdown = aggregate(
        wo_dicts,
        group_by=["execution_status"],
        metrics=[{"name": "count", "field": "*", "op": "count"}],
    )

    billing_blockers = aggregate(
        wo_dicts,
        group_by=["billing_status"],
        metrics=[{"name": "count", "field": "*", "op": "count"}],
    )

    join_result = join_by_company(deals, work_orders)

    cross_board_risks = []
    for company in join_result.companies:
        if company.match_confidence != "normalized_exact":
            continue
        has_pipeline = any(d.deal_status == "Open" for d in company.deals)
        has_ar = any(
            w.amount_receivable and w.amount_receivable > 0 for w in company.work_orders
        )
        if has_pipeline and has_ar:
            cross_board_risks.append({
                "company_code": company.company_code,
                "open_pipeline": company.total_open_pipeline_value,
                "total_ar": company.total_ar,
            })

    stale_deals = [d for d in open_deals if d.get("is_stale_close_date")]
    missing_values = sum(1 for d in deal_dicts if d.get("deal_value") is None)
    parse_failures = sum(
        1 for w in work_orders if any("parse_failed" in fw for fw in w.field_warnings)
    )
    sector_mismatches = sum(
        1 for c in join_result.companies
        if any("sector mismatch" in w for w in c.match_warnings)
    )

    return {
        "as_of": as_of,
        "source": "monday_api",
        "sections": {
            "pipeline_headline": {
                "open_deal_count": pipeline["open_deal_count"],
                "raw_pipeline_value_inr": pipeline["raw_pipeline_value"],
                "weighted_pipeline_value_inr": pipeline["weighted_pipeline_value"],
                "missing_deal_value_count": pipeline["missing_value_count"],
                "missing_probability_count": pipeline["missing_probability_count"],
                "probability_weights": weights,
            },
            "pipeline_by_stage": pipeline_by_stage.model_dump(mode="json"),
            "cash_collection": {
                "total_ar_inr": ar_agg.metrics.get("total_ar"),
                "priority_ar_inr": priority_ar.metrics.get("priority_ar"),
                "top_ar_companies": top_ar_groups,
                "ar_excluded_null_count": ar_agg.excluded_from_metrics.get("amount_receivable", 0),
            },
            "operations": {
                "execution_status": execution_breakdown.groups,
                "not_started": sum(
                    g.get("count", 0) for g in execution_breakdown.groups
                    if g.get("execution_status") == "Not Started"
                ),
                "ongoing": sum(
                    g.get("count", 0) for g in execution_breakdown.groups
                    if g.get("execution_status") == "Ongoing"
                ),
                "billing_status": billing_blockers.groups,
            },
            "cross_board_risks": {
                "companies_with_pipeline_and_ar": cross_board_risks[:10],
                "stale_open_deals_count": len(stale_deals),
                "match_summary": join_result.match_summary.model_dump(mode="json"),
            },
            "data_quality": {
                "work_order_count": len(work_orders),
                "deal_count": len(deals),
                "missing_deal_values": missing_values,
                "numeric_parse_failures": parse_failures,
                "sector_mismatch_companies": sector_mismatches,
                "wo_only_companies": join_result.unmatched.get("wo_only", []),
                "deal_only_company_count": join_result.unmatched.get("deal_only_count", 0),
                "warnings": join_result.warnings,
            },
        },
    }
