"""Regression tests for CompanyJoinResult Pydantic coercion."""

from __future__ import annotations

from src.models.company import CompanyJoinResult
from src.models.deal import Deal
from src.models.work_order import WorkOrder
from src.tools.join import join_by_company


def test_company_join_result_accepts_deal_instances():
    deal = Deal(item_id="d1", company_code="COMPANY001", deal_status="Open", deal_value=100.0)
    wo = WorkOrder(item_id="w1", company_code="COMPANY001", contract_value_incl_gst=200.0)
    result = CompanyJoinResult(
        company_code="COMPANY001",
        match_confidence="normalized_exact",
        match_method="numeric_id_normalization",
        deals=[deal],
        work_orders=[wo],
    )
    assert len(result.deals) == 1
    assert result.deals[0].item_id == "d1"
    assert len(result.work_orders) == 1


def test_join_by_company_output_validates():
    deals = [Deal(item_id="d1", company_code="COMPANY001", deal_status="Open")]
    wos = [WorkOrder(item_id="w1", company_code="COMPANY001")]
    join_result = join_by_company(deals, wos)
    assert join_result.companies
    company = join_result.companies[0]
    assert isinstance(company, CompanyJoinResult)
    assert company.deals[0].company_code == "COMPANY001"


def test_canonical_deal_import_path():
    from src.models.deal import Deal as DealA
    from src.models.records import Deal as DealB
    assert DealA is DealB


def test_canonical_work_order_import_path():
    from src.models.records import WorkOrder as WOB
    from src.models.work_order import WorkOrder as WOA
    assert WOA is WOB
