"""Monday.com GraphQL data models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MondayColumn(BaseModel):
    id: str
    title: str
    type: str
    settings_str: str | None = None


class MondayColumnValue(BaseModel):
    id: str
    text: str | None = None
    value: str | None = None
    type: str | None = None


class MondayItem(BaseModel):
    id: str
    name: str
    column_values: list[MondayColumnValue] = Field(default_factory=list)


class MondayBoard(BaseModel):
    id: str
    name: str
    columns: list[MondayColumn] = Field(default_factory=list)
    items_count: int | None = None


class FetchBoardItemsResult(BaseModel):
    records: list[MondayItem]
    pages: int
    total_items: int
    duration_ms: int
    source: str = "monday_api"
    board_id: str


class ParsedColumnValue(BaseModel):
    column_id: str
    column_title: str | None = None
    column_type: str | None = None
    text: str | None = None
    parsed_value: Any = None
    raw_value: str | None = None
    parse_warning: str | None = None


class ParsedItem(BaseModel):
    item_id: str
    item_name: str
    columns: dict[str, ParsedColumnValue]
    raw_column_values: dict[str, str | None] = Field(default_factory=dict)
