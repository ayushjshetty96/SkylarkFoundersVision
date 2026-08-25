"""Deterministic aggregation — the LLM must never compute business numbers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field


class AggregateResult(BaseModel):
    group_by: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    excluded_from_metrics: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    valid_row_count: int = 0
    total_row_count: int = 0


def _get_field(record: dict[str, Any], field: str) -> Any:
    if field in record:
        return record[field]
    # Support dotted access for nested dicts if needed
    parts = field.split(".")
    val: Any = record
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def _apply_filter(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        val = _get_field(record, key)
        if isinstance(expected, list):
            if val not in expected:
                return False
        elif val != expected:
            return False
    return True


def aggregate(
    records: list[dict[str, Any]],
    *,
    group_by: list[str] | None = None,
    metrics: list[dict[str, str]] | None = None,
    filters: dict[str, Any] | None = None,
) -> AggregateResult:
    """
    Aggregate records deterministically.

    metrics example:
        [{"name": "sum_deal_value", "field": "deal_value", "op": "sum"}]
        [{"name": "count", "field": "*", "op": "count"}]
        [{"name": "avg_ar", "field": "amount_receivable", "op": "avg"}]
    """
    group_by = group_by or []
    metrics = metrics or [{"name": "count", "field": "*", "op": "count"}]
    filters = filters or {}

    filtered = [r for r in records if _apply_filter(r, filters)]
    warnings: list[str] = []
    excluded: dict[str, int] = defaultdict(int)

    if not group_by:
        result_metrics: dict[str, Any] = {}
        for m in metrics:
            name = m["name"]
            field = m.get("field", "*")
            op = m.get("op", "count")
            result_metrics[name] = _compute_metric(filtered, field, op, excluded, warnings)
        if excluded:
            for field, count in excluded.items():
                warnings.append(f"{count} rows excluded from metrics due to missing {field}")
        return AggregateResult(
            group_by=[],
            metrics=result_metrics,
            groups=[],
            excluded_from_metrics=dict(excluded),
            warnings=warnings,
            valid_row_count=len(filtered),
            total_row_count=len(records),
        )

    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for record in filtered:
        key = tuple(_get_field(record, g) for g in group_by)
        buckets[key].append(record)

    groups: list[dict[str, Any]] = []
    for key, bucket in sorted(buckets.items(), key=lambda x: str(x[0])):
        group_row: dict[str, Any] = dict(zip(group_by, key, strict=False))
        for m in metrics:
            name = m["name"]
            field = m.get("field", "*")
            op = m.get("op", "count")
            group_row[name] = _compute_metric(bucket, field, op, excluded, warnings)
        group_row["_count"] = len(bucket)
        groups.append(group_row)

    overall: dict[str, Any] = {}
    for m in metrics:
        name = m["name"]
        field = m.get("field", "*")
        op = m.get("op", "count")
        overall[name] = _compute_metric(filtered, field, op, excluded, warnings)

    if excluded:
        for field, count in excluded.items():
            warnings.append(f"{count} rows excluded from metrics due to missing {field}")

    return AggregateResult(
        group_by=group_by,
        metrics=overall,
        groups=groups,
        excluded_from_metrics=dict(excluded),
        warnings=warnings,
        valid_row_count=len(filtered),
        total_row_count=len(records),
    )


def _compute_metric(
    records: list[dict[str, Any]],
    field: str,
    op: str,
    excluded: dict[str, int],
    warnings: list[str],
) -> Any:
    if op == "count":
        return len(records)

    values: list[float] = []
    null_count = 0
    for r in records:
        val = _get_field(r, field)
        if val is None:
            null_count += 1
            continue
        try:
            values.append(float(val))
        except (TypeError, ValueError):
            null_count += 1

    if null_count:
        excluded[field] = excluded.get(field, 0) + null_count

    if op == "sum":
        return sum(values) if values else None
    if op == "avg":
        return sum(values) / len(values) if values else None
    if op == "min":
        return min(values) if values else None
    if op == "max":
        return max(values) if values else None

    warnings.append(f"Unknown aggregation op: {op}")
    return None


def weighted_pipeline_sum(
    deals: list[dict[str, Any]],
    *,
    value_field: str = "deal_value",
    prob_field: str = "closure_probability",
    status_field: str = "deal_status",
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    weights = weights or {"High": 0.70, "Medium": 0.40, "Low": 0.15}
    open_deals = [d for d in deals if d.get(status_field) == "Open"]
    raw_sum = 0.0
    weighted_sum = 0.0
    missing_value = 0
    missing_prob = 0
    included = 0

    for d in open_deals:
        val = d.get(value_field)
        if val is None:
            missing_value += 1
            continue
        prob = d.get(prob_field)
        raw_sum += float(val)
        included += 1
        if prob and prob in weights:
            weighted_sum += float(val) * weights[prob]
        else:
            missing_prob += 1

    return {
        "open_deal_count": len(open_deals),
        "raw_pipeline_value": raw_sum,
        "weighted_pipeline_value": weighted_sum,
        "included_in_weighted": included - missing_prob,
        "missing_value_count": missing_value,
        "missing_probability_count": missing_prob,
        "weights_used": weights,
    }
