"""Parse Monday.com column_values into Python values."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.monday.models import MondayColumn, MondayItem, ParsedColumnValue, ParsedItem

logger = logging.getLogger(__name__)


def _safe_json_loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def parse_column_value(
    column_id: str,
    text: str | None,
    raw_value: str | None,
    column_type: str | None,
    column_title: str | None = None,
) -> ParsedColumnValue:
    warning: str | None = None
    parsed: Any = None

    if text is not None and text.strip() == "":
        text = None

    if raw_value is None and text is None:
        return ParsedColumnValue(
            column_id=column_id,
            column_title=column_title,
            column_type=column_type,
            text=text,
            parsed_value=None,
            raw_value=raw_value,
        )

    ctype = (column_type or "").lower()

    if ctype == "numbers":
        if text:
            try:
                parsed = float(text.replace(",", ""))
            except ValueError:
                parsed = None
                warning = "parse_failed"
        else:
            parsed = None

    elif ctype == "numeric":
        if text:
            try:
                parsed = float(text.replace(",", ""))
            except ValueError:
                parsed = None
                warning = "parse_failed"
        else:
            parsed = None

    elif ctype in ("status", "color"):
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            parsed = obj.get("label") or text
        else:
            parsed = text

    elif ctype == "dropdown":
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            parsed = obj.get("label") or text
        else:
            parsed = text

    elif ctype == "date":
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            parsed = obj.get("date") or text
        else:
            parsed = text

    elif ctype in ("people", "person"):
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            persons = obj.get("personsAndTeams") or obj.get("persons") or []
            names = [p.get("name", "") for p in persons if isinstance(p, dict)]
            parsed = ", ".join(n for n in names if n) or text
        else:
            parsed = text

    elif ctype == "long_text":
        parsed = text

    elif ctype == "text":
        parsed = text

    elif ctype == "checkbox":
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            parsed = obj.get("checked", False)
        else:
            parsed = text

    elif ctype == "timeline":
        obj = _safe_json_loads(raw_value)
        if isinstance(obj, dict):
            parsed = {
                "from": obj.get("from"),
                "to": obj.get("to"),
            }
        else:
            parsed = text

    else:
        # Preserve text for unknown types; don't discard
        parsed = text
        if ctype:
            logger.debug("Unknown column type '%s' for column %s", ctype, column_id)

    return ParsedColumnValue(
        column_id=column_id,
        column_title=column_title,
        column_type=column_type,
        text=text,
        parsed_value=parsed,
        raw_value=raw_value,
        parse_warning=warning,
    )


def build_column_lookup(columns: list[MondayColumn]) -> dict[str, MondayColumn]:
    return {c.id: c for c in columns}


def build_title_lookup(columns: list[MondayColumn]) -> dict[str, MondayColumn]:
    lookup: dict[str, MondayColumn] = {}
    for col in columns:
        key = col.title.strip().lower()
        if key not in lookup:
            lookup[key] = col
    return lookup


def parse_item(
    item: MondayItem,
    columns: list[MondayColumn],
) -> ParsedItem:
    col_by_id = build_column_lookup(columns)
    parsed_columns: dict[str, ParsedColumnValue] = {}
    raw_values: dict[str, str | None] = {}

    for cv in item.column_values:
        col = col_by_id.get(cv.id)
        title = col.title if col else None
        ctype = col.type if col else cv.type
        pcv = parse_column_value(cv.id, cv.text, cv.value, ctype, title)
        parsed_columns[cv.id] = pcv
        raw_values[cv.id] = cv.value

    return ParsedItem(
        item_id=item.id,
        item_name=item.name,
        columns=parsed_columns,
        raw_column_values=raw_values,
    )


def get_field_value(
    parsed_item: ParsedItem,
    column_map: dict[str, str],
    field_key: str,
    columns: list[MondayColumn],
    *,
    title_fallback: bool = True,
) -> ParsedColumnValue | None:
    """Resolve a logical field key to a parsed column value."""
    col_id = column_map.get(field_key)
    if col_id and col_id in parsed_item.columns:
        return parsed_item.columns[col_id]

    if title_fallback:
        title_lookup = build_title_lookup(columns)
        # field_key may be a title
        col = title_lookup.get(field_key.lower())
        if col and col.id in parsed_item.columns:
            return parsed_item.columns[col.id]

    return None
