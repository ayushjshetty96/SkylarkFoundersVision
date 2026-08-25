"""Tests for filtered pipeline analysis."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from src.models.records import Deal
from src.tools.pipeline_analysis import filter_open_deals, pipeline_analysis_tool


@pytest.fixture
def settings():
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
    )


def _deal(
    *,
    sector="Energy",
    status="Open",
    value=1_000_000.0,
    tentative=None,
    created=None,
) -> dict:
    return {
        "deal_status": status,
        "sector": sector,
        "sector_normalized": sector,
        "deal_value": value,
        "deal_stage": "Proposal",
        "tentative_close_date": tentative,
        "created_date": created,
        "closure_probability": "High",
    }


def test_filter_sector_and_quarter():
    from src.normalization.date_ranges import resolve_period

    deals = [
        _deal(sector="Energy", tentative="2026-08-15"),
        _deal(sector="Mining", tentative="2026-08-20"),
        _deal(sector="Energy", tentative="2026-01-15"),
        _deal(sector="Energy", status="Won", tentative="2026-08-15"),
    ]
    period = resolve_period("this_quarter", today=date(2026, 8, 25))
    filtered, meta = filter_open_deals(deals, sector="Energy", period=period)
    assert len(filtered) == 1
    assert meta["sector_filter"] == "Energy"
    assert meta["period"] == "Q3 2026"


def test_pipeline_analysis_tool_compact(monkeypatch, settings):
    ds = MagicMock()
    ds.get_deals.return_value = [
        Deal(
            item_id="1",
            company_code="COMPANY001",
            company_code_raw="COMPANY001",
            deal_status="Open",
            sector="Energy",
            sector_normalized="Energy",
            deal_value=2_000_000.0,
            deal_stage="Proposal",
            tentative_close_date=date(2026, 8, 10),
            closure_probability="High",
        ),
    ]
    result = pipeline_analysis_tool(
        ds,
        sector="Energy",
        period="this_quarter",
        settings=settings,
    )
    assert result["sector"] == "Energy"
    assert result["period"] == "Q3 2026"
    assert result["open_deal_count"] == 1
    assert result["pipeline_inr"] == 2_000_000.0
    assert "date_field_note" in result
    assert ds.get_deals.call_count == 1
