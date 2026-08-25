"""Unit tests for business_metric tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from config.settings import Settings
from src.tools.business_metric import business_metric_tool


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        GROQ_MODEL="openai/gpt-oss-120b",
    )


def test_receivables_metric():
    ds = MagicMock()
    ds.get_work_orders.return_value = [
        MagicMock(model_dump=lambda mode="json": {"amount_receivable": 100.0}),
        MagicMock(model_dump=lambda mode="json": {"amount_receivable": 50.0}),
        MagicMock(model_dump=lambda mode="json": {"amount_receivable": None}),
    ]
    result = business_metric_tool(ds, "receivables", settings=_settings())
    assert result["metric"] == "receivables"
    assert result["value"] == 150.0
    assert result["currency"] == "INR"
    assert "definition" in result


def test_total_revenue_summary_not_summed():
    ds = MagicMock()
    ds.get_work_orders.return_value = [
        MagicMock(model_dump=lambda mode="json": {
            "contract_value_incl_gst": 1000.0,
            "billed_value_incl_gst": 800.0,
            "collected_amount_incl_gst": 500.0,
            "amount_receivable": 100.0,
        }),
    ]
    ds.get_deals.return_value = []
    result = business_metric_tool(ds, "total_revenue", settings=_settings())
    assert result["metric"] == "revenue_summary"
    assert result["do_not_sum"] is True
    assert "metrics" in result
    assert "contract_value" in result["metrics"]
    assert "billed_revenue" in result["metrics"]
    assert "collected_revenue" in result["metrics"]
    assert "receivables" in result["metrics"]
    # Values must remain separate — no combined total
    values = [m["value"] for m in result["metrics"].values()]
    assert sum(values) != result.get("value")
    assert "do NOT add" in result["note"].lower() or "not add" in result["note"].lower()


def test_open_deal_count():
    ds = MagicMock()
    ds.get_deals.return_value = [
        MagicMock(model_dump=lambda mode="json": {"deal_status": "Open"}),
        MagicMock(model_dump=lambda mode="json": {"deal_status": "Closed"}),
    ]
    result = business_metric_tool(ds, "open_deal_count", settings=_settings())
    assert result["value"] == 1
