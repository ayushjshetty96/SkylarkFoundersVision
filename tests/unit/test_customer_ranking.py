"""Tests for customer_ranking tool ranking parameter."""

from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from src.tools.summary_tools import customer_ranking_tool


@pytest.fixture
def settings():
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
    )


def test_customer_ranking_best_delegates(monkeypatch, settings):
    ds = MagicMock()
    called = {}

    def fake_analysis(*args, **kwargs):
        called["operation"] = kwargs.get("operation") or args[1]
        return {"customers": [], "operation": called["operation"]}

    monkeypatch.setattr(
        "src.tools.summary_tools.customer_analysis_tool",
        fake_analysis,
    )
    result = customer_ranking_tool(ds, ranking="best", settings=settings)
    assert called["operation"] == "good_customers"
    assert "customers" in result


def test_customer_ranking_receivables_delegates(monkeypatch, settings):
    ds = MagicMock()
    called = {}

    def fake_analysis(*args, **kwargs):
        called["operation"] = kwargs.get("operation") or args[1]
        return {"customers": []}

    monkeypatch.setattr(
        "src.tools.summary_tools.customer_analysis_tool",
        fake_analysis,
    )
    customer_ranking_tool(ds, ranking="receivables", settings=settings)
    assert called["operation"] == "customer_receivables"


def test_customer_ranking_overview_delegates(monkeypatch, settings):
    ds = MagicMock()
    called = {}

    def fake_analysis(*args, **kwargs):
        called["operation"] = kwargs.get("operation") or args[1]
        return {"operation": called["operation"], "summary": {}}

    monkeypatch.setattr(
        "src.tools.summary_tools.customer_analysis_tool",
        fake_analysis,
    )
    customer_ranking_tool(ds, ranking="overview", settings=settings)
    assert called["operation"] == "customer_overview"


def test_customer_ranking_risk_delegates(monkeypatch, settings):
    ds = MagicMock()
    called = {}

    def fake_health(*args, **kwargs):
        called["health"] = True
        return {"customers": []}

    monkeypatch.setattr(
        "src.tools.summary_tools.customer_health_tool",
        fake_health,
    )
    customer_ranking_tool(ds, ranking="risk", settings=settings)
    assert called.get("health") is True
