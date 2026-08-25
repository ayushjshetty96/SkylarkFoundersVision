"""Business health score from deterministic metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "dashboard_rules.json"


def load_dashboard_rules() -> dict[str, Any]:
    if _RULES_PATH.exists():
        return json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return {}


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _customer_health_score(metrics: Any) -> float:
    rows = metrics.customers.get("rows") or []
    if not rows:
        return 70.0
    at_risk = sum(1 for r in rows if classify_customer_health(r) == "AT RISK")
    watch = sum(1 for r in rows if classify_customer_health(r) == "WATCH")
    penalty = (at_risk * 15 + watch * 5) / len(rows)
    return _clamp_score(100 - penalty)


def calculate_health_score(metrics: Any) -> dict[str, Any]:
    """Composite health score — live snapshot only, no fake trends."""
    rules = load_dashboard_rules()
    weights = rules.get("health_score_weights", {})

    rev = metrics.revenue
    pipe = metrics.pipeline
    ops = metrics.operations
    dq = metrics.data_quality

    billing_rate = rev.get("billing_rate") or 0
    collection_rate = rev.get("collection_rate") or 0
    revenue_health = _clamp_score((billing_rate + collection_rate) / 2 * 100)

    open_count = pipe.get("open_deal_count") or 0
    stale = pipe.get("stale_open_deals") or 0
    stale_ratio = stale / open_count if open_count else 0
    pipeline_health = _clamp_score(100 - stale_ratio * 100)

    ar = rev.get("receivables") or 0
    collected = rev.get("collected_revenue") or 1
    ar_ratio = ar / collected if collected else 0
    collections_health = _clamp_score(100 - min(ar_ratio, 1) * 80)

    stuck = ops.get("stuck") or 0
    not_started = ops.get("not_started") or 0
    wo_total = metrics.data_quality.get("work_order_count") or 1
    ops_penalty = (stuck * 5 + not_started * 0.5) / wo_total * 100
    operations_health = _clamp_score(100 - ops_penalty)

    customer_health = _customer_health_score(metrics)

    missing = dq.get("missing_deal_values") or 0
    deal_count = dq.get("deal_count") or 1
    dq_health = _clamp_score(100 - (missing / deal_count) * 100)

    w_rev = weights.get("revenue", 0.20)
    w_pipe = weights.get("pipeline", 0.20)
    w_coll = weights.get("collections", 0.20)
    w_ops = weights.get("operations", 0.20)
    w_cust = weights.get("customer_health", 0.20)
    w_dq = weights.get("data_quality", 0.0)

    overall = (
        revenue_health * w_rev
        + pipeline_health * w_pipe
        + collections_health * w_coll
        + operations_health * w_ops
        + customer_health * w_cust
        + dq_health * w_dq
    )

    return {
        "overall": round(overall, 1),
        "breakdown": {
            "revenue_health": round(revenue_health, 1),
            "pipeline_health": round(pipeline_health, 1),
            "collections_health": round(collections_health, 1),
            "operations_health": round(operations_health, 1),
            "customer_health": round(customer_health, 1),
            "data_quality_health": round(dq_health, 1),
        },
    }


def classify_customer_health(row: dict[str, Any]) -> str:
    """HEALTHY | WATCH | AT RISK from available fields only."""
    rules = load_dashboard_rules().get("customer_health", {})
    billed = row.get("billed") or 0
    receivables = row.get("receivables") or 0
    collected = row.get("collected") or 0
    ratio = receivables / billed if billed > 0 else (1.0 if receivables > 0 else 0.0)

    high_ratio = rules.get("high_receivables_ratio", 0.5)
    watch_ratio = rules.get("watch_receivables_ratio", 0.25)

    if ratio >= high_ratio or (receivables > 0 and collected == 0):
        return "AT RISK"
    if ratio >= watch_ratio or row.get("open_deals", 0) > 0 and receivables > 0:
        return "WATCH"
    if collected >= rules.get("min_collected_for_healthy", 100000):
        return "HEALTHY"
    return "WATCH"
