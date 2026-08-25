"""Unit tests for company join."""

from src.models.records import Deal, WorkOrder
from src.tools.join import join_by_company


def _wo(code: str, ar: float | None = None) -> WorkOrder:
    return WorkOrder(item_id=f"wo-{code}", company_code=code, company_code_raw=code, amount_receivable=ar)


def _deal(code: str, status: str = "Open", value: float | None = 100.0) -> Deal:
    return Deal(item_id=f"d-{code}", company_code=code, company_code_raw=code, deal_status=status, deal_value=value)


def test_normalized_exact_match():
    result = join_by_company(
        [_deal("COMPANY002")],
        [_wo("COMPANY002", ar=500.0)],
    )
    assert result.match_summary.normalized_exact == 1


def test_wo_only_company():
    result = join_by_company([], [_wo("COMPANY042")])
    assert result.match_summary.unmatched_wo_only == 1
    assert "COMPANY042" in result.unmatched["wo_only"]


def test_deal_only_company():
    result = join_by_company([_deal("COMPANY099")], [])
    assert result.match_summary.unmatched_deal_only == 1


def test_cross_board_aggregation():
    result = join_by_company(
        [_deal("COMPANY005", value=1000.0)],
        [_wo("COMPANY005", ar=200.0)],
    )
    company = result.companies[0]
    assert company.total_open_pipeline_value == 1000.0
    assert company.total_ar == 200.0
