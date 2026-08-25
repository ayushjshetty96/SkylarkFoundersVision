"""Quantity parsing preserving numeric value and unit."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.normalization.numeric import safe_numeric


@dataclass
class QuantityResult:
    value: float | None
    unit: str | None
    raw: str | None = None
    warning: str | None = None


_QUANTITY_RE = re.compile(
    r"^\s*(-?[\d,]+(?:\.\d+)?)\s*([A-Za-z][A-Za-z/\s]*)?\s*$"
)
_EMBEDDED_RE = re.compile(r"(-?[\d,]+(?:\.\d+)?)\s*([A-Za-z][A-Za-z]*)")


def parse_quantity(raw: str | float | int | None) -> QuantityResult:
    if raw is None:
        return QuantityResult(value=None, unit=None)

    if isinstance(raw, (int, float)):
        return QuantityResult(value=float(raw), unit=None, raw=str(raw))

    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none"):
        return QuantityResult(value=None, unit=None, raw=text)

    # Pure numeric
    num_only = safe_numeric(text)
    if num_only.value is not None and num_only.warning is None:
        if not re.search(r"[A-Za-z]", text):
            return QuantityResult(value=num_only.value, unit=None, raw=text)

    match = _QUANTITY_RE.match(text)
    if match:
        num = safe_numeric(match.group(1))
        unit = match.group(2).strip() if match.group(2) else None
        return QuantityResult(
            value=num.value,
            unit=unit,
            raw=text,
            warning=num.warning,
        )

    embedded = _EMBEDDED_RE.search(text)
    if embedded:
        num = safe_numeric(embedded.group(1))
        unit = embedded.group(2).strip()
        return QuantityResult(value=num.value, unit=unit, raw=text, warning=num.warning)

    num = safe_numeric(text)
    return QuantityResult(value=num.value, unit=None, raw=text, warning=num.warning or "unparsed_unit")
