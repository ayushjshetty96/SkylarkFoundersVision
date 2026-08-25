"""Unit tests for dashboard data preparation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from config.settings import Settings
from src.ui.dashboard_data import (
    build_dashboard_bundle,
    build_risk_radar,
    compact_briefing_facts,
)


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        GROQ_MODEL="openai/gpt-oss-120b",
    )


def _mock_leadership() -> dict:
    return {
        "as_of": "2026-08-25",
        "sections": {
            "pipeline_headline": {
                "open_deal_count": 49,
                "raw_pipeline_value_inr": 688_000_000.0,
                "weighted_pipeline_value_inr": 213_000_000.0,
                "missing_deal_value_count": 2,
            },
            "pipeline_by_stage": {
                "groups": [
                    {"deal_stage": "Feasibility", "deal_count": 10, "pipeline_value": 100_000_000},
                    {"deal_stage": "Proposal", "deal_count": 15, "pipeline_value": 200_000_000},
                ],
            },
            "cash_collection": {
                "total_ar_inr": 36_291_748.87,
                "priority_ar_inr": 5_600_000.0,
                "top_ar_companies": [],
            },
            "operations": {
                "execution_status": [
                    {"execution_status": "Not Started", "count": 12},
                    {"execution_status": "Ongoing", "count": 30},
                    {"execution_status": "Completed", "count": 100},
                    {"execution_status": "Paused/Stuck", "count": 3},
                ],
                "not_started": 12,
                "ongoing": 30,
                "billing_status": [
                    {"billing_status": "Update Required", "count": 5},
                ],
            },
            "cross_board_risks": {
                "stale_open_deals_count": 48,
                "companies_with_pipeline_and_ar": [{"company_code": "COMPANY001"}],
            },
            "data_quality": {
                "work_order_count": 180,
                "deal_count": 347,
                "missing_deal_values": 10,
                "numeric_parse_failures": 2,
                "sector_mismatch_companies": 1,
                "deal_only_company_count": 147,
            },
        },
    }


def _mock_revenue() -> dict:
    return {
        "metric": "revenue_summary",
        "do_not_sum": True,
        "metrics": {
            "contract_value": {"value": 248_523_995.05},
            "billed_revenue": {"value": 126_719_936.37},
            "collected_revenue": {"value": 90_428_187.50},
            "receivables": {"value": 36_291_748.87},
        },
    }


def _mock_rankings() -> dict:
    empty = {"customers": [], "customer_count": 50}
    return {
        "collected": empty,
        "billed": empty,
        "receivables": empty,
        "contract": empty,
        "attention": empty,
        "overview": empty,
    }


def test_financial_ratios_not_summed():
    leadership = _mock_leadership()
    revenue = _mock_revenue()
    risks = build_risk_radar(leadership, revenue)
    assert len(risks) > 0

    ds = MagicMock()
    ds.get_work_orders.return_value = []
    ds.get_deals.return_value = []

    with patch("src.ui.dashboard_data.generate_leadership_snapshot", return_value=leadership), \
         patch("src.ui.dashboard_data.business_metric_tool", return_value=revenue), \
         patch("src.ui.dashboard_data.build_customer_rankings_bundle", return_value=_mock_rankings()):
        bundle = build_dashboard_bundle(ds, settings=_settings())

    fin = bundle.financial
    assert fin["contract_value"] == 248_523_995.05
    assert fin["billed_revenue"] == 126_719_936.37
    assert fin["collected_revenue"] == 90_428_187.50
    # Ratios are mathematical, not summed totals
    assert fin["billing_realization"] is not None
    assert fin["collection_realization"] is not None
    total_wrong = fin["contract_value"] + fin["billed_revenue"] + fin["collected_revenue"]
    assert total_wrong != fin.get("receivables")


def test_risk_radar_from_leadership():
    risks = build_risk_radar(_mock_leadership(), _mock_revenue())
    labels = [r["label"] for r in risks]
    assert any("stale" in l.lower() for l in labels)
    assert any("priority" in l.lower() for l in labels)
    assert any("not started" in l.lower() for l in labels)


def test_compact_briefing_facts_no_raw_records():
    ds = MagicMock()
    ds.get_work_orders.return_value = []
    ds.get_deals.return_value = []
    with patch("src.ui.dashboard_data.generate_leadership_snapshot", return_value=_mock_leadership()), \
         patch("src.ui.dashboard_data.business_metric_tool", return_value=_mock_revenue()), \
         patch("src.ui.dashboard_data.build_customer_rankings_bundle", return_value=_mock_rankings()):
        bundle = build_dashboard_bundle(ds, settings=_settings())
    facts = compact_briefing_facts(bundle)
    assert "open_pipeline_inr" in facts
    assert "records" not in str(facts)
    assert facts["contract_value_inr"] == 248_523_995.05


def test_pipeline_stages_from_leadership():
    ds = MagicMock()
    ds.get_work_orders.return_value = []
    ds.get_deals.return_value = []
    with patch("src.ui.dashboard_data.generate_leadership_snapshot", return_value=_mock_leadership()), \
         patch("src.ui.dashboard_data.business_metric_tool", return_value=_mock_revenue()), \
         patch("src.ui.dashboard_data.build_customer_rankings_bundle", return_value=_mock_rankings()):
        bundle = build_dashboard_bundle(ds, settings=_settings())
    stages = bundle.pipeline["stages"]
    assert len(stages) == 2
    assert stages[0]["deal_stage"] == "Feasibility"
