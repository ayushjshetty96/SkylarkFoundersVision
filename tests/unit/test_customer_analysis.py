"""Unit tests for customer_analysis tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from config.settings import Settings
from src.models.records import CompanyJoinResult, Deal, JoinByCompanyResult, JoinSummary, WorkOrder
from src.tools.customer_analysis import customer_analysis_tool


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        GROQ_MODEL="openai/gpt-oss-120b",
    )


def _make_join_result() -> JoinByCompanyResult:
    wo1 = WorkOrder(
        item_id="1",
        company_code="COMPANY001",
        contract_value_incl_gst=1000.0,
        billed_value_incl_gst=800.0,
        collected_amount_incl_gst=600.0,
        amount_receivable=50.0,
    )
    wo2 = WorkOrder(
        item_id="2",
        company_code="COMPANY002",
        contract_value_incl_gst=500.0,
        billed_value_incl_gst=400.0,
        collected_amount_incl_gst=100.0,
        amount_receivable=200.0,
    )
    deal1 = Deal(item_id="d1", company_code="COMPANY001", deal_status="Open", deal_value=300.0)
    return JoinByCompanyResult(
        match_summary=JoinSummary(normalized_exact=2),
        companies=[
            CompanyJoinResult(
                company_code="COMPANY001",
                match_confidence="normalized_exact",
                match_method="numeric_id_normalization",
                deals=[deal1],
                work_orders=[wo1],
                total_open_pipeline_value=300.0,
                total_ar=50.0,
            ),
            CompanyJoinResult(
                company_code="COMPANY002",
                match_confidence="normalized_exact",
                match_method="numeric_id_normalization",
                deals=[],
                work_orders=[wo2],
                total_open_pipeline_value=None,
                total_ar=200.0,
            ),
        ],
        unmatched={"wo_only": [], "deal_only": [], "deal_only_count": 0},
    )


def test_top_customers_by_collected():
    ds = MagicMock()
    with patch("src.tools.customer_analysis.join_by_company", return_value=_make_join_result()):
        result = customer_analysis_tool(ds, "top_customers", sort_by="collected", settings=_settings())
    assert result["operation"] == "top_customers"
    assert result["customers"][0]["company_code"] == "COMPANY001"
    assert result["customers"][0]["collected"] == 600.0
    assert "records" not in result


def test_good_customers_deterministic():
    ds = MagicMock()
    with patch("src.tools.customer_analysis.join_by_company", return_value=_make_join_result()):
        r1 = customer_analysis_tool(ds, "good_customers", settings=_settings())
        r2 = customer_analysis_tool(ds, "good_customers", settings=_settings())
    assert r1["customers"] == r2["customers"]
    assert "NOT profitability" in r1["definition"] or "not profitability" in r1["definition"].lower()


def test_customer_overview():
    ds = MagicMock()
    with patch("src.tools.customer_analysis.join_by_company", return_value=_make_join_result()):
        result = customer_analysis_tool(ds, "customer_overview", settings=_settings())
    assert result["operation"] == "customer_overview"
    assert result["customer_count"] == 2
    assert "top_by_collected" in result["summary"]


def test_customer_receivables_ranking():
    ds = MagicMock()
    with patch("src.tools.customer_analysis.join_by_company", return_value=_make_join_result()):
        result = customer_analysis_tool(ds, "customer_receivables", settings=_settings())
    assert result["customers"][0]["company_code"] == "COMPANY002"
    assert result["customers"][0]["receivables"] == 200.0


def test_pipeline_and_receivables():
    ds = MagicMock()
    with patch("src.tools.customer_analysis.join_by_company", return_value=_make_join_result()):
        result = customer_analysis_tool(ds, "pipeline_and_receivables", settings=_settings())
    assert result["customer_count"] == 1
    assert result["customers"][0]["company_code"] == "COMPANY001"


def test_company_code_only_join():
    ds = MagicMock()
    ds.get_deals.return_value = []
    ds.get_work_orders.return_value = []
    with patch("src.tools.customer_analysis.join_by_company") as mock_join:
        mock_join.return_value = JoinByCompanyResult(
            match_summary=JoinSummary(),
            companies=[],
            unmatched={},
        )
        customer_analysis_tool(ds, "top_customers", settings=_settings())
        mock_join.assert_called_once()
