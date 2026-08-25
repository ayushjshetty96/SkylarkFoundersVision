"""Tests for DataService TTL caching."""

import time
from unittest.mock import MagicMock, patch

from config.settings import Settings
from src.data_service import DataService
from src.models.records import Deal, WorkOrder


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        DASHBOARD_CACHE_TTL=180,
    )


def _mock_client():
    client = MagicMock()
    board = MagicMock()
    board.id = "1"
    board.name = "Board"
    board.items_count = 1
    board.columns = []
    client.get_board_schema.return_value = board
    fetch = MagicMock()
    fetch.records = []
    client.fetch_board_items.return_value = fetch
    return client


@patch("src.data_service.normalize_work_orders")
@patch("src.data_service.normalize_deals")
def test_work_orders_cached(mock_norm_deals, mock_norm_wo):
    mock_norm_wo.return_value = [
        WorkOrder(item_id="1", company_code="COMPANY001", company_code_raw="C1"),
    ]
    mock_norm_deals.return_value = []

    ds = DataService(_settings())
    ds._client = _mock_client()

    first = ds.get_work_orders()
    second = ds.get_work_orders()

    assert first is second
    assert ds._client.fetch_board_items.call_count == 1


@patch("src.data_service.normalize_work_orders")
def test_invalidate_cache_refetches(mock_norm_wo):
    mock_norm_wo.return_value = [
        WorkOrder(item_id="1", company_code="COMPANY001", company_code_raw="C1"),
    ]

    ds = DataService(_settings())
    ds._client = _mock_client()

    ds.get_work_orders()
    ds.invalidate_cache()
    ds.get_work_orders()

    assert ds._client.fetch_board_items.call_count == 2


@patch("src.data_service.normalize_deals")
def test_deals_cached(mock_norm_deals):
    mock_norm_deals.return_value = [
        Deal(item_id="d1", company_code="COMPANY001", company_code_raw="C1"),
    ]

    ds = DataService(_settings())
    ds._client = _mock_client()

    ds.get_deals()
    ds.get_deals()

    assert ds._client.fetch_board_items.call_count == 1
