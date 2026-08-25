"""Deterministic business KPIs — compact interface for the LLM."""

from __future__ import annotations

from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.tools.aggregate import aggregate, weighted_pipeline_sum

CURRENCY = "INR"

METRIC_DEFINITIONS: dict[str, dict[str, str]] = {
    "total_contract_value": {
        "definition": "Total work order contract value (incl. GST) — Amount in Rupees (Incl of GST)",
        "board": "work_orders",
        "field": "contract_value_incl_gst",
    },
    "contract_value": {
        "definition": "Total work order contract value (incl. GST) — Amount in Rupees (Incl of GST)",
        "board": "work_orders",
        "field": "contract_value_incl_gst",
    },
    "billed_revenue": {
        "definition": "Total billed value on work orders (incl. GST)",
        "board": "work_orders",
        "field": "billed_value_incl_gst",
    },
    "collected_revenue": {
        "definition": "Total collected amount on work orders (incl. GST) — realized cash",
        "board": "work_orders",
        "field": "collected_amount_incl_gst",
    },
    "receivables": {
        "definition": "Outstanding amount receivable (AR) on work orders",
        "board": "work_orders",
        "field": "amount_receivable",
    },
    "open_pipeline": {
        "definition": "Sum of deal values where Deal Status == Open",
        "board": "deals",
        "field": "deal_value",
    },
    "open_deal_count": {
        "definition": "Count of deals with Deal Status == Open",
        "board": "deals",
    },
    "open_deals": {
        "definition": "Count of deals with Deal Status == Open",
        "board": "deals",
    },
    "open_work_orders": {
        "definition": "Work orders with Execution Status == Ongoing",
        "board": "work_orders",
    },
    "deal_count": {
        "definition": "Total deal count",
        "board": "deals",
    },
    "work_order_count": {
        "definition": "Total work order count",
        "board": "work_orders",
    },
    "not_started_work_orders": {
        "definition": "Work orders with Execution Status == Not Started",
        "board": "work_orders",
    },
}

SUPPORTED_METRICS = list(METRIC_DEFINITIONS.keys())


def business_metric_tool(
    data_service: DataService,
    metric: str,
    settings: Settings | None = None,
    *,
    work_orders: list | None = None,
    deals: list | None = None,
) -> dict[str, Any]:
    """Return a single compact KPI from live Monday data."""
    settings = settings or get_settings()
    metric = metric.strip().lower().replace(" ", "_")

    # Aliases
    if metric == "total_revenue" or metric == "revenue":
        return _revenue_summary(data_service, settings, work_orders=work_orders, deals=deals)

    if metric == "open_deals":
        metric = "open_deal_count"
    if metric == "total_contract_value":
        metric = "contract_value"

    if metric not in METRIC_DEFINITIONS:
        return {
            "error": f"Unknown metric: {metric}",
            "supported_metrics": SUPPORTED_METRICS,
        }

    meta = METRIC_DEFINITIONS[metric]
    definition = meta["definition"]

    if metric == "open_deal_count":
        if deals is None:
            deals_raw = [d.model_dump(mode="json") for d in data_service.get_deals()]
        else:
            deals_raw = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in deals]
        open_deals = [d for d in deals_raw if d.get("deal_status") == "Open"]
        return {
            "metric": metric,
            "value": len(open_deals),
            "definition": definition,
            "source": "deals",
            "record_count": len(deals_raw),
            "currency": None,
        }

    if metric == "deal_count":
        if deals is None:
            deal_list = data_service.get_deals()
        else:
            deal_list = deals
        return {
            "metric": metric,
            "value": len(deal_list),
            "definition": definition,
            "source": "deals",
            "record_count": len(deal_list),
            "currency": None,
        }

    if metric == "open_work_orders":
        if work_orders is None:
            wos_raw = [w.model_dump(mode="json") for w in data_service.get_work_orders()]
        else:
            wos_raw = [w.model_dump(mode="json") if hasattr(w, "model_dump") else w for w in work_orders]
        filtered = [w for w in wos_raw if w.get("execution_status") == "Ongoing"]
        return {
            "metric": metric,
            "value": len(filtered),
            "definition": definition,
            "source": "work_orders",
            "record_count": len(wos_raw),
            "currency": None,
        }

    if metric == "work_order_count":
        if work_orders is None:
            wo_list = data_service.get_work_orders()
        else:
            wo_list = work_orders
        return {
            "metric": metric,
            "value": len(wo_list),
            "definition": definition,
            "source": "work_orders",
            "record_count": len(wo_list),
            "currency": None,
        }

    if metric == "not_started_work_orders":
        if work_orders is None:
            wos_raw = [w.model_dump(mode="json") for w in data_service.get_work_orders()]
        else:
            wos_raw = [w.model_dump(mode="json") if hasattr(w, "model_dump") else w for w in work_orders]
        filtered = [w for w in wos_raw if w.get("execution_status") == "Not Started"]
        return {
            "metric": metric,
            "value": len(filtered),
            "definition": definition,
            "source": "work_orders",
            "record_count": len(wos_raw),
            "currency": None,
        }

    if metric == "open_pipeline":
        if deals is None:
            deals_raw = [d.model_dump(mode="json") for d in data_service.get_deals()]
        else:
            deals_raw = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in deals]
        open_deals = [d for d in deals_raw if d.get("deal_status") == "Open"]
        weights = {
            "High": settings.prob_weight_high,
            "Medium": settings.prob_weight_medium,
            "Low": settings.prob_weight_low,
        }
        pipeline = weighted_pipeline_sum(deals, weights=weights)
        return {
            "metric": metric,
            "value": pipeline["raw_pipeline_value"],
            "weighted_value": pipeline["weighted_pipeline_value"],
            "definition": definition,
            "source": "deals",
            "record_count": pipeline["open_deal_count"],
            "missing_value_count": pipeline["missing_value_count"],
            "currency": CURRENCY,
        }

    # Sum metrics on work orders or deals
    board = meta["board"]
    field = meta["field"]
    if board == "work_orders":
        if work_orders is None:
            records = [w.model_dump(mode="json") for w in data_service.get_work_orders()]
        else:
            records = [w.model_dump(mode="json") if hasattr(w, "model_dump") else w for w in work_orders]
    else:
        if deals is None:
            records = [d.model_dump(mode="json") for d in data_service.get_deals()]
        else:
            records = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in deals]

    agg = aggregate(
        records,
        metrics=[{"name": "value", "field": field, "op": "sum"}],
    )
    return {
        "metric": metric,
        "value": agg.metrics.get("value"),
        "definition": definition,
        "source": board,
        "record_count": agg.valid_row_count,
        "excluded_null_count": agg.excluded_from_metrics.get(field, 0),
        "warnings": agg.warnings[:3],
        "currency": CURRENCY,
    }


def _revenue_summary(
    data_service: DataService,
    settings: Settings,
    *,
    work_orders: list | None = None,
    deals: list | None = None,
) -> dict[str, Any]:
    """Return separate revenue-related metrics — never summed."""
    kw = {"work_orders": work_orders, "deals": deals}
    contract = business_metric_tool(data_service, "contract_value", settings, **kw)
    billed = business_metric_tool(data_service, "billed_revenue", settings, **kw)
    collected = business_metric_tool(data_service, "collected_revenue", settings, **kw)
    receivables = business_metric_tool(data_service, "receivables", settings, **kw)

    return {
        "metric": "revenue_summary",
        "title": "Revenue-related financial summary",
        "do_not_sum": True,
        "note": (
            "Contract value, billed revenue, collected revenue, and receivables are "
            "separate financial measures. Do NOT add them together."
        ),
        "metrics": {
            "contract_value": {
                "value": contract.get("value"),
                "definition": contract.get("definition"),
                "excluded_null_count": contract.get("excluded_null_count", 0),
            },
            "billed_revenue": {
                "value": billed.get("value"),
                "definition": billed.get("definition"),
                "excluded_null_count": billed.get("excluded_null_count", 0),
            },
            "collected_revenue": {
                "value": collected.get("value"),
                "definition": collected.get("definition"),
                "excluded_null_count": collected.get("excluded_null_count", 0),
            },
            "receivables": {
                "value": receivables.get("value"),
                "definition": receivables.get("definition"),
                "excluded_null_count": receivables.get("excluded_null_count", 0),
            },
        },
        "currency": CURRENCY,
        "source": "work_orders",
    }
