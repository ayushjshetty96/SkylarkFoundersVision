"""Tests for executive intelligence engine."""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.dashboard.customer_tiers import classify_customer_tier, customer_concentration
from src.dashboard.data import CachedMondayData
from src.dashboard.health import calculate_health_score
from src.dashboard.intelligence_engine import (
    build_intelligence,
    compute_revenue_gaps,
    build_sector_ranking,
)
from src.dashboard.metrics import DashboardMetrics
from src.dashboard.pipeline_radar import build_pipeline_radar, classify_deal_opportunity
from src.models.deal import Deal
from src.models.work_order import WorkOrder


def _metrics_and_data():
    rows = [
        {
            "company_code": "COMPANY001",
            "collected": 20_000_000,
            "billed": 25_000_000,
            "receivables": 5_000_000,
            "open_pipeline": 10_000_000,
            "work_orders": 5,
            "open_deals": 2,
        },
        {
            "company_code": "COMPANY002",
            "collected": 1_000_000,
            "billed": 2_000_000,
            "receivables": 8_000_000,
            "open_pipeline": 0,
            "work_orders": 1,
            "open_deals": 0,
        },
    ]
    metrics = DashboardMetrics(
        revenue={
            "contract_value": 100_000_000,
            "billed_revenue": 50_000_000,
            "collected_revenue": 30_000_000,
            "receivables": 20_000_000,
            "collection_rate": 0.6,
            "billing_rate": 0.5,
        },
        pipeline={
            "open_pipeline": 80_000_000,
            "open_deal_count": 10,
            "stale_open_deals": 2,
            "stages": [{"deal_stage": "Proposal", "pipeline_value": 40_000_000}],
            "missing_deal_value_count": 1,
        },
        operations={"stuck": 2, "not_started": 5, "completed": 20, "open_work_orders": 15},
        customers={"rows": rows, "top_collected": rows},
        sectors={
            "by_pipeline": [{"sector_normalized": "Energy", "pipeline": 50_000_000}],
            "by_contract_value": [{"sector_normalized": "Energy", "contract_value": 30_000_000}],
            "by_work_orders": [{"sector_normalized": "Energy", "wo_count": 10}],
        },
        data_quality={"work_order_count": 50, "deal_count": 100, "missing_deal_values": 5},
    )
    data = CachedMondayData(
        work_orders=[
            WorkOrder(
                item_id="w1",
                company_code="COMPANY001",
                execution_status="Stuck",
                end_date=date(2020, 1, 1),
            ),
        ],
        deals=[
            Deal(
                item_id="d1",
                company_code="COMPANY001",
                deal_status="Open",
                deal_value=15_000_000,
                closure_probability="High",
                sector_normalized="Energy",
            ),
            Deal(
                item_id="d2",
                company_code="COMPANY002",
                deal_status="Open",
                deal_value=1_000_000,
                closure_probability="Low",
                is_stale_close_date=True,
            ),
        ],
        loaded_at=datetime.now(timezone.utc),
        work_order_count=1,
        deal_count=2,
    )
    return metrics, data


def test_business_health_five_drivers():
    metrics, _ = _metrics_and_data()
    health = calculate_health_score(metrics)
    assert 0 <= health["overall"] <= 100
    bd = health["breakdown"]
    assert "customer_health" in bd
    assert "revenue_health" in bd


def test_revenue_gaps_not_additive():
    gaps = compute_revenue_gaps({
        "contract_value": 100,
        "billed_revenue": 80,
        "collected_revenue": 50,
        "receivables": 30,
    })
    assert gaps["unbilled_gap"] == 20
    assert gaps["uncollected_from_billed"] == 30


def test_pipeline_radar_classification():
    deal = {
        "deal_status": "Open",
        "deal_value": 15_000_000,
        "closure_probability": "High",
        "is_stale_close_date": False,
    }
    assert classify_deal_opportunity(deal) == "HIGH VALUE"
    stale = {**deal, "is_stale_close_date": True}
    assert classify_deal_opportunity(stale) == "STALE"


def test_customer_tier_and_concentration():
    rows = [
        {"company_code": "A", "collected": 80, "billed": 100, "receivables": 10, "open_pipeline": 0, "work_orders": 1},
        {"company_code": "B", "collected": 20, "billed": 30, "receivables": 5, "open_pipeline": 0, "work_orders": 1},
    ]
    conc = customer_concentration(rows, top_n=1)
    assert conc["share_pct"] == 80.0
    assert classify_customer_tier(rows[0]) in ("STRATEGIC", "STABLE", "GROWING", "WATCH", "AT RISK")


def test_build_intelligence_bundle():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    assert intel.health["overall"] >= 0
    assert len(intel.risks) > 0
    assert len(intel.this_week) > 0
    assert intel.pipeline_radar.get("counts") is not None
    assert all("title" in i and "action" in i for i in intel.insights)


def test_sector_ranking():
    metrics, _ = _metrics_and_data()
    ranked = build_sector_ranking(metrics)
    assert ranked[0]["sector"] == "Energy"
    assert ranked[0]["rank"] == 1


def test_cross_board_rows_have_tier():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    assert intel.cross_board[0].get("tier") is not None
    assert intel.cross_board[0].get("health") is not None


def test_founder_actions_ranked():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    assert len(intel.founder_actions) > 0
    assert intel.founder_actions[0]["rank"] == 1
    assert "category" in intel.founder_actions[0]


def test_data_integrity_in_bundle():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    assert intel.data_integrity.get("confidence") in ("HIGH", "MEDIUM", "LOW")
    assert intel.data_integrity.get("live_snapshot_note")


def test_risks_categorized():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    assert isinstance(intel.risks_by_category, dict)
    assert "CASH_RISK" in intel.risks_by_category or "OPERATIONAL_RISK" in intel.risks_by_category


def test_no_fabricated_historical_trends():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    note = intel.data_integrity.get("live_snapshot_note", "")
    assert "historical trend unavailable" in note.lower()
