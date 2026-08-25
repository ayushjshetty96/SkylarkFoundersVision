"""Board schema tool — compact field list."""

from __future__ import annotations

from typing import Any

from src.data_layer import load_column_map
from src.data_service import DataService


def get_board_schema(data_service: DataService, board: str) -> dict[str, Any]:
    full = data_service.fetch_board_schema(board)
    board_key = "work_orders" if "work" in board.lower() else "deals"
    col_map = load_column_map().get(board_key, {}).get("columns", {})
    logical_fields = list(col_map.keys()) if col_map else [
        c.get("title") for c in (full.get("columns") or []) if isinstance(c, dict)
    ]
    return {
        "board": full.get("board"),
        "board_name": full.get("board_name"),
        "item_count_estimate": full.get("item_count_estimate"),
        "column_count": full.get("column_count"),
        "fields": logical_fields,
    }
