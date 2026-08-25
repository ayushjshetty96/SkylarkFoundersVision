"""Tests for dashboard metrics, health, and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.dashboard.alerts import generate_alerts
from src.dashboard.data import CachedMondayData, minutes_since_sync
from src.dashboard.health import calculate_health_score, classify_customer_health
from src.dashboard.metrics import DashboardMetrics, calculate_all_metrics
from src.models.deal import Deal
from src.models.work_order import WorkOrder


def _cached_data() -> CachedMondayData:
    return CachedMondayData(
        work_orders=[
            WorkOrder(
                item_id="w1",
                company_code="COMPANY001",
                contract_value_incl_gst=1000.0,
                billed_value_incl_gst=800.0,
                collected_amount_incl_gst=600.0,
                amount_receivable=100.0,
                execution_status="Ongoing",
            ),
        ],
        deals=[
            Deal(item_id="d1", company_code="COMPANY001", deal_status="Open", deal_value=500.0),
            Deal(item_id="d2", company_code="COMPANY002", deal_status="Open", deal_value=None),
        ],
        loaded_at=datetime.now(timezone.utc),
        work_order_count=1,
        deal_count=2,
    )


def test_calculate_all_metrics_mocked():
    ds = MagicMock()
    metrics = calculate_all_metrics(ds, _cached_data(), top_n=5)
    assert isinstance(metrics, DashboardMetrics)
    assert metrics.revenue.get("contract_value") == 1000.0
    assert metrics.pipeline.get("open_deal_count") == 2
    assert metrics.data_quality.get("missing_deal_values") == 1


def test_health_score():
    metrics = DashboardMetrics(
        revenue={"billing_rate": 0.8, "collection_rate": 0.7, "receivables": 100, "collected_revenue": 1000},
        pipeline={"open_deal_count": 10, "stale_open_deals": 1},
        operations={"stuck": 0, "not_started": 2},
        data_quality={"missing_deal_values": 2, "deal_count": 100},
    )
    health = calculate_health_score(metrics)
    assert 0 <= health["overall"] <= 100
    assert "breakdown" in health


def test_customer_health_classification():
    assert classify_customer_health({"billed": 100, "receivables": 60, "collected": 0}) == "AT RISK"
    assert classify_customer_health({"billed": 1000, "receivables": 10, "collected": 500000}) == "HEALTHY"


def test_generate_alerts():
    metrics = DashboardMetrics(
        revenue={"receivables": 5_000_000},
        pipeline={"stale_open_deals": 20, "open_deal_count": 49},
        operations={"stuck": 2, "not_started": 10},
        data_quality={"deal_only_company_count": 147, "missing_deal_values": 50},
    )
    alerts = generate_alerts(metrics)
    assert len(alerts) > 0


def test_minutes_since_sync():
    from datetime import timedelta
    loaded = datetime.now(timezone.utc) - timedelta(minutes=2)
    mins = minutes_since_sync(loaded)
    assert 1.5 < mins < 3.0
