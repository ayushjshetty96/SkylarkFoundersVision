"""Company code normalization for cross-board joins."""

from __future__ import annotations

import re


def normalize_company_code(raw: str | None) -> str | None:
    """
    Normalize company identifiers to canonical COMPANYnnn format.

    Examples:
        WOCOMPANY_002 -> COMPANY002
        COMPANY002    -> COMPANY002
        COMPANY2      -> COMPANY002
    """
    if raw is None:
        return None

    text = str(raw).strip().upper()
    if not text or text in ("NAN", "NONE", ""):
        return None

    match = re.search(r"(\d+)", text)
    if not match:
        return None

    num = int(match.group(1))
    return f"COMPANY{num:03d}"
