"""Join by company tool."""

from __future__ import annotations

from typing import Any

from src.data_service import DataService
from src.models.records import Deal, WorkOrder
from src.tools.join import join_by_company as _join_by_company


def join_by_company_tool(
    data_service: DataService,
    company_codes: list[str] | None = None,
    deals: list[dict[str, Any]] | None = None,
    work_orders: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if deals is None:
        deals = [d.model_dump(mode="json") for d in data_service.get_deals()]
    if work_orders is None:
        work_orders = [w.model_dump(mode="json") for w in data_service.get_work_orders()]

    deal_models = [Deal.model_validate(d) for d in deals]
    wo_models = [WorkOrder.model_validate(w) for w in work_orders]

    result = _join_by_company(deal_models, wo_models, company_codes=company_codes)
    return result.model_dump(mode="json")
