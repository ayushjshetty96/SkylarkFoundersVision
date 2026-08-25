"""Resolve relative date periods for deterministic BI filtering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    label: str
    period_key: str


def current_quarter_bounds(today: date) -> tuple[date, date]:
    """Return (start, end) for the calendar quarter containing *today*."""
    quarter = (today.month - 1) // 3
    start_month = quarter * 3 + 1
    start = date(today.year, start_month, 1)
    if start_month == 10:
        end = date(today.year, 12, 31)
    else:
        end = date(today.year, start_month + 3, 1) - timedelta(days=1)
    return start, end


def resolve_period(
    period: str | None,
    *,
    today: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> DateRange | None:
    """
    Resolve a period keyword or explicit date range.

    Supported keywords: today, this_week, this_month, this_quarter, this_year
    """
    if start and end:
        return DateRange(start=start, end=end, label=f"{start.isoformat()} to {end.isoformat()}", period_key="custom")

    if not period:
        return None

    key = period.strip().lower().replace(" ", "_").replace("-", "_")
    today = today or date.today()

    if key in ("today",):
        return DateRange(start=today, end=today, label="today", period_key="today")

    if key in ("this_week", "week"):
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return DateRange(start=week_start, end=week_end, label="this week", period_key="this_week")

    if key in ("this_month", "month"):
        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            month_end = date(today.year, 12, 31)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return DateRange(start=month_start, end=month_end, label="this month", period_key="this_month")

    if key in ("this_quarter", "quarter"):
        q_start, q_end = current_quarter_bounds(today)
        q_num = (today.month - 1) // 3 + 1
        return DateRange(
            start=q_start,
            end=q_end,
            label=f"Q{q_num} {today.year}",
            period_key="this_quarter",
        )

    if key in ("this_year", "year"):
        return DateRange(
            start=date(today.year, 1, 1),
            end=date(today.year, 12, 31),
            label=f"{today.year}",
            period_key="this_year",
        )

    return None


def date_in_range(value: date | None, period: DateRange) -> bool:
    if value is None:
        return False
    return period.start <= value <= period.end
