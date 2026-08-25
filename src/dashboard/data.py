"""Cached Monday data loading boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.data_service import DataService
from src.models.deal import Deal
from src.models.work_order import WorkOrder
from src.utils.timer import timed


@dataclass
class CachedMondayData:
    work_orders: list[WorkOrder]
    deals: list[Deal]
    loaded_at: datetime
    work_order_count: int
    deal_count: int


def load_monday_data(data_service: DataService) -> CachedMondayData:
    """Fetch and normalize Work Orders + Deals once."""
    with timed("Monday Work Orders fetch"):
        work_orders = data_service.get_work_orders()
    with timed("Monday Deals fetch"):
        deals = data_service.get_deals()
    return CachedMondayData(
        work_orders=work_orders,
        deals=deals,
        loaded_at=datetime.now(timezone.utc),
        work_order_count=len(work_orders),
        deal_count=len(deals),
    )


def minutes_since_sync(loaded_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    if loaded_at.tzinfo is None:
        loaded_at = loaded_at.replace(tzinfo=timezone.utc)
    return (now - loaded_at).total_seconds() / 60.0
