"""Deterministic pipeline opportunity classification."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.dashboard.health import load_dashboard_rules


def classify_deal_opportunity(deal: dict[str, Any], *, today: date | None = None) -> str:
    """
    Classify open deals: HIGH VALUE | QUICK WIN | STALE | AT RISK.
    Deterministic rules only.
    """
    today = today or date.today()
    rules = load_dashboard_rules().get("pipeline_radar", {})
    high_value_threshold = rules.get("high_value_inr", 10_000_000)
    quick_win_threshold = rules.get("quick_win_inr", 2_000_000)
    high_prob = {"High", "high"}

    value = deal.get("deal_value") or 0
    prob = deal.get("closure_probability") or ""
    is_stale = deal.get("is_stale_close_date", False)

    if is_stale:
        return "STALE"
    if value >= high_value_threshold and prob not in high_prob:
        return "AT RISK"
    if value >= high_value_threshold:
        return "HIGH VALUE"
    if prob in high_prob and value >= quick_win_threshold:
        return "QUICK WIN"
    if prob in high_prob:
        return "QUICK WIN"
    if value > 0 and prob not in high_prob and prob not in ("Medium", "Low"):
        return "AT RISK"
    return "AT RISK" if is_stale else "QUICK WIN"


def build_pipeline_radar(open_deals: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify all open deals and return summary + top items per category."""
    buckets: dict[str, list[dict]] = {
        "HIGH VALUE": [],
        "QUICK WIN": [],
        "STALE": [],
        "AT RISK": [],
    }
    for deal in open_deals:
        if deal.get("deal_status") != "Open":
            continue
        label = classify_deal_opportunity(deal)
        buckets[label].append({
            "deal_name": (deal.get("deal_name") or "—")[:40],
            "company_code": deal.get("company_code"),
            "deal_value": deal.get("deal_value"),
            "deal_stage": deal.get("deal_stage"),
            "closure_probability": deal.get("closure_probability"),
            "sector": deal.get("sector_normalized") or deal.get("sector"),
        })

    for key in buckets:
        buckets[key] = sorted(
            buckets[key],
            key=lambda d: d.get("deal_value") or 0,
            reverse=True,
        )[:8]

    largest = None
    valued = [d for d in open_deals if d.get("deal_value")]
    if valued:
        largest = max(valued, key=lambda d: d.get("deal_value") or 0)

    return {
        "counts": {k: len(v) for k, v in buckets.items()},
        "buckets": buckets,
        "largest_opportunity": {
            "deal_name": largest.get("deal_name") if largest else None,
            "company_code": largest.get("company_code") if largest else None,
            "deal_value": largest.get("deal_value") if largest else None,
        } if largest else None,
    }
