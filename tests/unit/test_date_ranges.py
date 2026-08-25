"""Tests for date period resolution."""

from datetime import date

from src.normalization.date_ranges import (
    current_quarter_bounds,
    date_in_range,
    resolve_period,
)


def test_current_quarter_q1():
    today = date(2026, 2, 15)
    start, end = current_quarter_bounds(today)
    assert start == date(2026, 1, 1)
    assert end == date(2026, 3, 31)


def test_current_quarter_q4():
    today = date(2026, 11, 1)
    start, end = current_quarter_bounds(today)
    assert start == date(2026, 10, 1)
    assert end == date(2026, 12, 31)


def test_resolve_this_quarter():
    dr = resolve_period("this_quarter", today=date(2026, 8, 25))
    assert dr is not None
    assert dr.start == date(2026, 7, 1)
    assert dr.end == date(2026, 9, 30)
    assert "Q3" in dr.label


def test_resolve_this_month():
    dr = resolve_period("this_month", today=date(2026, 8, 25))
    assert dr is not None
    assert dr.start == date(2026, 8, 1)
    assert dr.end == date(2026, 8, 31)


def test_resolve_this_week():
    dr = resolve_period("this_week", today=date(2026, 8, 25))  # Tuesday
    assert dr is not None
    assert dr.start == date(2026, 8, 24)  # Monday
    assert dr.end == date(2026, 8, 30)


def test_date_in_range():
    dr = resolve_period("today", today=date(2026, 8, 25))
    assert dr is not None
    assert date_in_range(date(2026, 8, 25), dr)
    assert not date_in_range(date(2026, 8, 24), dr)
