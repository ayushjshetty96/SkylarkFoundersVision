"""Unit tests for quantity parsing."""

import pytest

from src.normalization.quantity import parse_quantity


@pytest.mark.parametrize(
    "raw,value,unit",
    [
        ("5360 HA", 5360.0, "HA"),
        ("2057 Acr", 2057.0, "Acr"),
        ("57.55 HA", 57.55, "HA"),
        ("3956HA", 3956.0, "HA"),
        ("2186.54 HA", 2186.54, "HA"),
        ("100", 100.0, None),
    ],
)
def test_parse_quantity(raw, value, unit):
    result = parse_quantity(raw)
    assert result.value == pytest.approx(value)
    assert result.unit == unit
