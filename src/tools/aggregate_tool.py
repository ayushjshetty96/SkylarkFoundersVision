"""Aggregate tool wrapper."""

from __future__ import annotations

from typing import Any

from src.tools.aggregate import aggregate as _aggregate


def aggregate_tool(
    records: list[dict[str, Any]],
    group_by: list[str] | None = None,
    metrics: list[dict[str, str]] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _aggregate(records, group_by=group_by, metrics=metrics, filters=filters)
    return result.model_dump(mode="json")
