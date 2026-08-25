"""Unit tests for numeric parsing."""

import pytest

from src.normalization.numeric import safe_numeric


def test_value_error():
    result = safe_numeric("#VALUE!")
    assert result.value is None
    assert result.warning == "parse_failed"


def test_blank_numeric():
    result = safe_numeric("")
    assert result.value is None


def test_negative_ar():
    result = safe_numeric("-160.2371")
    assert result.value == pytest.approx(-160.2371)
    assert result.warning is None


def test_comma_separated():
    result = safe_numeric("1,234,567.89")
    assert result.value == pytest.approx(1234567.89)


def test_integer():
    result = safe_numeric(42)
    assert result.value == 42.0
