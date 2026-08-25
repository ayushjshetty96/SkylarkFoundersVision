"""Numeric parsing with explicit failure handling."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NumericResult:
    value: float | None
    warning: str | None = None
    raw: str | None = None


def safe_numeric(raw: str | float | int | None) -> NumericResult:
    if raw is None:
        return NumericResult(value=None, raw=None)

    if isinstance(raw, (int, float)):
        return NumericResult(value=float(raw), raw=str(raw))

    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", ""):
        return NumericResult(value=None, raw=text or None)

    if "#VALUE" in text.upper() or text.startswith("#"):
        return NumericResult(value=None, warning="parse_failed", raw=text)

    cleaned = text.replace(",", "")
    try:
        return NumericResult(value=float(cleaned), raw=text)
    except ValueError:
        return NumericResult(value=None, warning="parse_failed", raw=text)
