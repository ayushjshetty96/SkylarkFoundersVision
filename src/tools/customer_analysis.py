"""Server-side customer/company analysis — compact output for the LLM."""

from __future__ import annotations

from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.models.company import CompanyJoinResult
from src.models.deal import Deal
from src.models.work_order import WorkOrder
from src.tools.join import join_by_company

CURRENCY = "INR"

SUPPORTED_OPERATIONS = [
    "top_customers",
    "good_customers",
    "customer_overview",
    "customer_receivables",
    "customer_pipeline",
    "pipeline_and_receivables",
]

SORT_FIELDS = [
    "collected",
    "billed",
    "contract_value",
    "receivables",
    "open_pipeline",
    "work_orders",
    "open_deals",
    "good_customer_score",
]


def _sum_wo_field(work_orders: list[WorkOrder], field: str) -> float | None:
    values = [getattr(w, field) for w in work_orders if getattr(w, field) is not None]
    return sum(values) if values else None


def _company_row(company: CompanyJoinResult) -> dict[str, Any]:
    wos = company.work_orders
    deals = company.deals
    open_deals = [d for d in deals if d.deal_status == "Open"]

    contract_value = _sum_wo_field(wos, "contract_value_incl_gst")
    billed = _sum_wo_field(wos, "billed_value_incl_gst")
    collected = _sum_wo_field(wos, "collected_amount_incl_gst")
    receivables = _sum_wo_field(wos, "amount_receivable")
    open_pipeline = company.total_open_pipeline_value

    return {
        "company_code": company.company_code,
        "match_confidence": company.match_confidence,
        "contract_value": contract_value,
        "billed": billed,
        "collected": collected,
        "receivables": receivables,
        "open_pipeline": open_pipeline,
        "work_orders": len(wos),
        "open_deals": len(open_deals),
        "deal_count": len(deals),
    }


def _good_customer_score(row: dict[str, Any]) -> float:
    """Proxy score from available data — NOT profitability."""
    collected = row.get("collected") or 0.0
    billed = row.get("billed") or 0.0
    contract = row.get("contract_value") or 0.0
    pipeline = row.get("open_pipeline") or 0.0
    receivables = row.get("receivables") or 0.0
    activity = (row.get("work_orders") or 0) + (row.get("open_deals") or 0)

    score = collected * 0.45 + billed * 0.25 + contract * 0.15 + pipeline * 0.10
    score += activity * 1_000_000  # tie-breaker for active customers

    if billed > 0 and receivables > 0:
        ar_ratio = min(receivables / billed, 1.0)
        score -= ar_ratio * collected * 0.15  # penalize high AR relative to billed

    return score


def _build_company_rows(join_result) -> list[dict[str, Any]]:
    rows = []
    for company in join_result.companies:
        if company.match_confidence == "normalized_exact":
            row = _company_row(company)
            row["good_customer_score"] = _good_customer_score(row)
            rows.append(row)
    return rows


def _sort_rows(rows: list[dict[str, Any]], sort_by: str, descending: bool = True) -> list[dict[str, Any]]:
    key = sort_by if sort_by in SORT_FIELDS else "collected"

    def sort_key(r: dict[str, Any]) -> float:
        val = r.get(key)
        return float(val) if val is not None else float("-inf" if descending else "inf")

    return sorted(rows, key=sort_key, reverse=descending)


def _data_quality(join_result) -> dict[str, Any]:
    unmatched = join_result.unmatched or {}
    return {
        "matched_companies": join_result.match_summary.normalized_exact,
        "wo_only_companies": join_result.match_summary.unmatched_wo_only,
        "deal_only_companies": join_result.match_summary.unmatched_deal_only,
        "total_companies_in_join": len(join_result.companies),
    }


def _quality_caveats(dq: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    if dq.get("deal_only_companies"):
        caveats.append(
            f"{dq['deal_only_companies']} companies appear on Deals only — no matching Work Orders by company code."
        )
    if dq.get("wo_only_companies"):
        caveats.append(
            f"{dq['wo_only_companies']} companies appear on Work Orders only — no matching Deals by company code."
        )
    return caveats


def customer_analysis_tool(
    data_service: DataService,
    operation: str,
    *,
    limit: int = 10,
    sort_by: str = "collected",
    settings: Settings | None = None,
    work_orders: list[WorkOrder] | None = None,
    deals: list[Deal] | None = None,
) -> dict[str, Any]:
    """Deterministic customer analysis using company-code join only."""
    settings = settings or get_settings()
    operation = operation.strip().lower().replace(" ", "_")
    limit = max(1, min(int(limit), 25))

    if operation not in SUPPORTED_OPERATIONS:
        return {
            "error": f"Unknown operation: {operation}",
            "supported_operations": SUPPORTED_OPERATIONS,
        }

    if deals is None:
        deals = data_service.get_deals()
    if work_orders is None:
        work_orders = data_service.get_work_orders()
    join_result = join_by_company(deals, work_orders)
    rows = _build_company_rows(join_result)
    dq = _data_quality(join_result)

    if operation == "good_customers":
        ranked = _sort_rows(rows, "good_customer_score")
        return {
            "operation": operation,
            "definition": (
                "Proxy for 'good customer' based on collected/billed/contract value, "
                "active business, and relatively lower receivables. "
                "This is NOT profitability — cost/margin data is unavailable."
            ),
            "customers": ranked[:limit],
            "customer_count": len(rows),
            "currency": CURRENCY,
            "data_quality": dq,
            "do_not_sum_financials": True,
        }

    if operation == "customer_overview":
        by_collected = _sort_rows(rows, "collected")[:limit]
        by_receivables = _sort_rows(rows, "receivables")[:limit]
        by_pipeline = _sort_rows(rows, "open_pipeline")[:limit]
        by_activity = sorted(rows, key=lambda r: (r.get("work_orders") or 0), reverse=True)[:limit]
        pipeline_and_ar = [
            r for r in rows
            if (r.get("open_pipeline") or 0) > 0 and (r.get("receivables") or 0) > 0
        ][:limit]
        major_cross_board = [
            {
                "company_code": r.get("company_code"),
                "collected": r.get("collected"),
                "billed": r.get("billed"),
                "receivables": r.get("receivables"),
                "open_pipeline": r.get("open_pipeline"),
                "work_orders": r.get("work_orders"),
                "open_deals": r.get("open_deals"),
            }
            for r in _sort_rows(rows, "collected")[: min(limit, 8)]
        ]

        return {
            "operation": operation,
            "customer_count": len(rows),
            "summary": {
                "top_by_collected": by_collected[:5],
                "top_by_receivables": by_receivables[:5],
                "top_by_pipeline": by_pipeline[:5],
                "most_work_orders": by_activity[:5],
                "pipeline_and_receivables": pipeline_and_ar[:5],
                "major_customers_cross_board": major_cross_board,
            },
            "currency": CURRENCY,
            "data_quality": dq,
            "data_quality_caveats": _quality_caveats(dq),
            "note": "Executive customer overview — strongest customers, attention areas, and cross-board snapshot.",
        }

    if operation == "customer_receivables":
        ranked = _sort_rows(rows, "receivables")
        return {
            "operation": operation,
            "sort_by": "receivables",
            "customers": ranked[:limit],
            "customer_count": len(rows),
            "currency": CURRENCY,
            "data_quality": dq,
        }

    if operation == "customer_pipeline":
        ranked = _sort_rows(rows, "open_pipeline")
        return {
            "operation": operation,
            "sort_by": "open_pipeline",
            "customers": ranked[:limit],
            "customer_count": len(rows),
            "currency": CURRENCY,
            "data_quality": dq,
        }

    if operation == "pipeline_and_receivables":
        filtered = [
            r for r in rows
            if (r.get("open_pipeline") or 0) > 0 and (r.get("receivables") or 0) > 0
        ]
        ranked = _sort_rows(filtered, "receivables")
        return {
            "operation": operation,
            "customers": ranked[:limit],
            "customer_count": len(filtered),
            "currency": CURRENCY,
            "data_quality": dq,
            "note": "Companies with both open pipeline and outstanding receivables.",
        }

    # top_customers (default)
    ranked = _sort_rows(rows, sort_by)
    return {
        "operation": "top_customers",
        "sort_by": sort_by,
        "customers": ranked[:limit],
        "customer_count": len(rows),
        "currency": CURRENCY,
        "data_quality": dq,
    }


def build_customer_rankings_bundle(
    data_service: DataService,
    *,
    top_n: int = 10,
    settings: Settings | None = None,
    work_orders: list[WorkOrder] | None = None,
    deals: list[Deal] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build all customer ranking views from a single join — one Monday fetch."""
    settings = settings or get_settings()
    if deals is None:
        deals = data_service.get_deals()
    if work_orders is None:
        work_orders = data_service.get_work_orders()

    join_result = join_by_company(deals, work_orders)
    rows = _build_company_rows(join_result)
    dq = _data_quality(join_result)
    limit = max(1, min(int(top_n), 25))

    def _base(operation: str, customers: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        return {
            "operation": operation,
            "customers": customers,
            "customer_count": len(rows),
            "currency": CURRENCY,
            "data_quality": dq,
            **extra,
        }

    pipeline_and_ar = [
        r for r in rows
        if (r.get("open_pipeline") or 0) > 0 and (r.get("receivables") or 0) > 0
    ]

    return {
        "collected": _base(
            "top_customers",
            _sort_rows(rows, "collected")[:limit],
            sort_by="collected",
        ),
        "billed": _base(
            "top_customers",
            _sort_rows(rows, "billed")[:limit],
            sort_by="billed",
        ),
        "receivables": _base(
            "customer_receivables",
            _sort_rows(rows, "receivables")[:limit],
            sort_by="receivables",
        ),
        "contract": _base(
            "top_customers",
            _sort_rows(rows, "contract_value")[:limit],
            sort_by="contract_value",
        ),
        "attention": _base(
            "pipeline_and_receivables",
            _sort_rows(pipeline_and_ar, "receivables")[:limit],
            note="Companies with both open pipeline and outstanding receivables.",
        ),
        "overview": {
            "operation": "customer_overview",
            "customer_count": len(rows),
            "summary": {
                "top_by_collected": _sort_rows(rows, "collected")[:5],
                "top_by_receivables": _sort_rows(rows, "receivables")[:5],
                "top_by_pipeline": _sort_rows(rows, "open_pipeline")[:5],
                "most_work_orders": sorted(rows, key=lambda r: r.get("work_orders") or 0, reverse=True)[:5],
                "pipeline_and_receivables": _sort_rows(pipeline_and_ar, "receivables")[:5],
            },
            "currency": CURRENCY,
            "data_quality": dq,
            "note": "Compact overview — not a full customer dump.",
        },
    }
