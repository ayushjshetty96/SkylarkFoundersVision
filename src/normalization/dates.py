"""Date and month-name parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


@dataclass
class DateResult:
    value: date | None
    warning: str | None = None
    raw: str | None = None
    is_month_only: bool = False
    month_name: str | None = None


@dataclass
class MonthResult:
    month_name: str | None
    month_number: int | None
    raw: str | None = None


def parse_iso_date(raw: str | None) -> DateResult:
    if raw is None:
        return DateResult(value=None)

    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none"):
        return DateResult(value=None, raw=text)

    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return DateResult(value=datetime.strptime(text[:10], "%Y-%m-%d").date(), raw=text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return DateResult(value=parsed.date(), raw=text)
    except (ValueError, TypeError):
        return DateResult(value=None, warning="parse_failed", raw=text)


def parse_month_name(raw: str | None) -> MonthResult:
    if raw is None:
        return MonthResult(month_name=None, month_number=None)

    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none"):
        return MonthResult(month_name=None, month_number=None, raw=text)

    key = text.lower().rstrip(".")
    month_num = MONTH_NAMES.get(key)
    if month_num:
        return MonthResult(month_name=text, month_number=month_num, raw=text)

    return MonthResult(month_name=text, month_number=None, raw=text, )
