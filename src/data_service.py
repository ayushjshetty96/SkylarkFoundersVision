"""Data access service with Monday API integration and caching."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

from config.settings import Settings, get_settings
from src.data_layer import normalize_deals, normalize_work_orders
from src.models.records import Deal, WorkOrder
from src.monday.client import MondayClient
from src.monday.models import MondayBoard

logger = logging.getLogger(__name__)


class DataService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = MondayClient(
            api_token=self.settings.monday_api_token,
            api_url=self.settings.monday_api_url,
        )
        self._schema_cache: dict[str, tuple[MondayBoard, float]] = {}
        self._wo_cache: list[WorkOrder] | None = None
        self._deals_cache: list[Deal] | None = None
        self._wo_loaded_at: float = 0.0
        self._deals_loaded_at: float = 0.0

    @property
    def client(self) -> MondayClient:
        return self._client

    def invalidate_cache(self) -> None:
        """Clear in-memory board caches (e.g. on dashboard Refresh)."""
        self._wo_cache = None
        self._deals_cache = None
        self._wo_loaded_at = 0.0
        self._deals_loaded_at = 0.0
        self._schema_cache.clear()
        logger.debug("DataService cache invalidated")

    def _board_ttl(self) -> int:
        return int(self.settings.dashboard_cache_ttl)

    def _schema_ttl(self) -> int:
        return int(self.settings.schema_cache_ttl)

    def _is_fresh(self, loaded_at: float, ttl: int) -> bool:
        return loaded_at > 0 and (time.monotonic() - loaded_at) < ttl

    def _get_board_schema_cached(self, board_id: str) -> MondayBoard:
        now = time.monotonic()
        cached = self._schema_cache.get(board_id)
        if cached and self._is_fresh(cached[1], self._schema_ttl()):
            return cached[0]
        board = self._client.get_board_schema(board_id)
        self._schema_cache[board_id] = (board, now)
        return board

    def get_work_orders_board_id(self) -> str:
        return self.settings.monday_work_orders_board_id

    def get_deals_board_id(self) -> str:
        return self.settings.monday_deals_board_id

    def fetch_board_schema(self, board: str) -> dict[str, Any]:
        board_id = self._resolve_board_id(board)
        monday_board = self._get_board_schema_cached(board_id)
        return {
            "board": board,
            "board_id": monday_board.id,
            "board_name": monday_board.name,
            "item_count_estimate": monday_board.items_count,
            "columns": [
                {
                    "id": c.id,
                    "title": c.title,
                    "type": c.type,
                    "settings_str": c.settings_str,
                }
                for c in monday_board.columns
            ],
            "column_count": len(monday_board.columns),
        }

    def query_items(
        self,
        board: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if board in ("work_orders", "work orders", "wo"):
            records = self.get_work_orders()
            record_dicts = [r.model_dump(mode="json") for r in records]
            board_id = self.get_work_orders_board_id()
        else:
            records = self.get_deals()
            record_dicts = [r.model_dump(mode="json") for r in records]
            board_id = self.get_deals_board_id()

        if filters:
            record_dicts = [r for r in record_dicts if _matches_filters(r, filters)]

        return {
            "board": board,
            "filters_applied": filters or {},
            "row_count": len(record_dicts),
            "records": record_dicts,
            "truncated": False,
            "fetch_metadata": {
                "source": "monday_api_cached",
                "board_id": board_id,
                "cache_ttl_seconds": self._board_ttl(),
            },
        }

    def get_work_orders(self, *, force_refresh: bool = False) -> list[WorkOrder]:
        if not force_refresh and self._wo_cache is not None and self._is_fresh(self._wo_loaded_at, self._board_ttl()):
            return self._wo_cache

        board_id = self.get_work_orders_board_id()
        schema = self._get_board_schema_cached(board_id)
        items = self._client.fetch_board_items(board_id)
        self._wo_cache = normalize_work_orders(items.records, schema.columns)
        self._wo_loaded_at = time.monotonic()
        return self._wo_cache

    def get_deals(self, as_of: date | None = None, *, force_refresh: bool = False) -> list[Deal]:
        if (
            not force_refresh
            and as_of is None
            and self._deals_cache is not None
            and self._is_fresh(self._deals_loaded_at, self._board_ttl())
        ):
            return self._deals_cache

        board_id = self.get_deals_board_id()
        schema = self._get_board_schema_cached(board_id)
        items = self._client.fetch_board_items(board_id)
        deals = normalize_deals(items.records, schema.columns, as_of=as_of)
        if as_of is None:
            self._deals_cache = deals
            self._deals_loaded_at = time.monotonic()
        return deals

    def _resolve_board_id(self, board: str) -> str:
        key = board.lower().strip().replace(" ", "_")
        if key in ("work_orders", "workorders", "wo", "work_order"):
            return self.get_work_orders_board_id()
        if key in ("deals", "deal", "deal_funnel"):
            return self.get_deals_board_id()
        raise ValueError(f"Unknown board: {board}. Use 'work_orders' or 'deals'.")


def _matches_filters(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        val = record.get(key)
        if isinstance(expected, list):
            if val not in expected:
                return False
        elif val != expected:
            return False
    return True


def create_data_service(settings: Settings | None = None) -> DataService:
    return DataService(settings=settings)
