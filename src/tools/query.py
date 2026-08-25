"""Query items tool — compact by default."""

from __future__ import annotations

from typing import Any

from src.data_service import DataService

DEFAULT_QUERY_FIELDS_WO = [
    "project_alias", "company_code", "serial_number", "sector",
    "execution_status", "amount_receivable", "contract_value_incl_gst",
    "billed_value_incl_gst", "billing_status",
]
DEFAULT_QUERY_FIELDS_DEALS = [
    "deal_name", "company_code", "deal_status", "deal_stage",
    "deal_value", "sector", "closure_probability",
]


def query_items(
    data_service: DataService,
    board: str,
    filters: dict[str, Any] | None = None,
    *,
    include_records: bool = False,
    limit: int = 5,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    full = data_service.query_items(board, filters=filters)
    records = full.get("records") or []

    if not include_records:
        return {
            "board": full.get("board"),
            "row_count": full.get("row_count", len(records)),
            "filters_applied": full.get("filters_applied", {}),
            "note": (
                "Summary only. Use business_metric for KPIs or aggregate for grouped metrics. "
                "Set include_records=true with limit for sample rows."
            ),
        }

    field_list = fields or (
        DEFAULT_QUERY_FIELDS_WO if "work" in board.lower() else DEFAULT_QUERY_FIELDS_DEALS
    )
    trimmed = []
    for rec in records[:limit]:
        trimmed.append({k: rec.get(k) for k in field_list if k in rec})

    return {
        "board": full.get("board"),
        "row_count": full.get("row_count", len(records)),
        "filters_applied": full.get("filters_applied", {}),
        "returned_count": len(trimmed),
        "truncated": len(records) > limit,
        "records": trimmed,
    }
