"""Unit tests for Monday column parser."""

import json

from src.monday.models import MondayColumn, MondayColumnValue, MondayItem
from src.monday.parser import parse_column_value, parse_item


def test_parse_numbers():
    result = parse_column_value("num1", "1234.56", None, "numbers")
    assert result.parsed_value == 1234.56


def test_parse_status():
    raw = json.dumps({"label": "Completed"})
    result = parse_column_value("status1", "Completed", raw, "status")
    assert result.parsed_value == "Completed"


def test_parse_date():
    raw = json.dumps({"date": "2025-05-16"})
    result = parse_column_value("date1", "2025-05-16", raw, "date")
    assert result.parsed_value == "2025-05-16"


def test_parse_item_full():
    columns = [
        MondayColumn(id="text1", title="Serial #", type="text"),
        MondayColumn(id="num1", title="Amount", type="numbers"),
    ]
    item = MondayItem(
        id="123",
        name="SDPLDEAL-001",
        column_values=[
            MondayColumnValue(id="text1", text="SDPLDEAL-001", value=None, type="text"),
            MondayColumnValue(id="num1", text="500", value=None, type="numbers"),
        ],
    )
    parsed = parse_item(item, columns)
    assert parsed.item_id == "123"
    assert parsed.columns["num1"].parsed_value == 500.0
