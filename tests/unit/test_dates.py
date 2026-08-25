"""Unit tests for date parsing."""

from datetime import date

from src.normalization.dates import parse_iso_date, parse_month_name


def test_iso_date():
    result = parse_iso_date("2025-05-16")
    assert result.value == date(2025, 5, 16)


def test_month_name():
    result = parse_month_name("December")
    assert result.month_number == 12
    assert result.month_name == "December"


def test_month_june():
    result = parse_month_name("June")
    assert result.month_number == 6
