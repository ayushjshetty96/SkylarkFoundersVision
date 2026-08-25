"""Server-side aggregate — fetches data internally, no records from LLM."""

from __future__ import annotations

from typing import Any

from src.data_service import DataService
from src.tools.aggregate_tool import aggregate_tool


def server_aggregate_tool(
    data_service: DataService,
    *,
    board: str,
    group_by: list[str] | None = None,
    metrics: list[dict[str, str]] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate on a board without passing raw records through the LLM."""
    if board in ("work_orders", "work orders", "wo"):
        records = [w.model_dump(mode="json") for w in data_service.get_work_orders()]
    elif board in ("deals", "deal"):
        records = [d.model_dump(mode="json") for d in data_service.get_deals()]
    else:
        return {"error": f"Unknown board: {board}. Use work_orders or deals."}

    return aggregate_tool(
        records=records,
        group_by=group_by,
        metrics=metrics,
        filters=filters,
    )
