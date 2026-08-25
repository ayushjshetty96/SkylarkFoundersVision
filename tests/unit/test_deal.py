"""Unit tests for stale deal detection."""

from datetime import date

from src.models.records import Deal


def test_stale_open_deal():
    deal = Deal(
        item_id="1",
        deal_status="Open",
        tentative_close_date=date(2024, 1, 1),
        is_stale_close_date=True,
    )
    assert deal.is_stale_close_date is True


def test_missing_deal_value():
    deal = Deal(item_id="1", deal_value=None)
    assert deal.deal_value is None
