"""Sector normalization for cross-board comparison."""

from __future__ import annotations

SECTOR_ALIASES: dict[str, str] = {
    "dsp": "DSP",
    "tender": "Tender",
    "sector/service": "Unknown",
    "security and surveillance": "Security and Surveillance",
    "manufacturing": "Manufacturing",
    "aviation": "Aviation",
    "renewables": "Renewables",
    "energy": "Energy",
    "mining": "Mining",
    "railways": "Railways",
    "powerline": "Powerline",
    "construction": "Construction",
    "others": "Others",
}


def normalize_sector(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", ""):
        return None
    return SECTOR_ALIASES.get(text.lower(), text.strip())


def normalize_sector_query(query: str | None) -> str | None:
    """Normalize a user/tool sector filter."""
    if not query:
        return None
    return normalize_sector(query.strip()) or query.strip()


def sector_matches(record_sector: str | None, query_sector: str | None) -> bool:
    """Return True if record sector matches the query (after normalization)."""
    if not query_sector:
        return True
    query_norm = (normalize_sector_query(query_sector) or "").lower()
    if not query_norm:
        return True
    record_norm = (normalize_sector(record_sector) or record_sector or "").lower()
    if not record_norm:
        return False
    if record_norm == query_norm:
        return True
    if query_norm in record_norm or record_norm in query_norm:
        return True
    # Renewables often labeled as energy-related in founder questions
    energy_group = {"energy", "renewables", "powerline"}
    if query_norm in energy_group and record_norm in energy_group:
        return True
    return False


def normalize_billing_status(raw: str | None) -> tuple[str | None, str | None]:
    """Return (normalized_value, normalization_note)."""
    if raw is None:
        return None, None
    text = str(raw).strip()
    if not text:
        return None, None
    if text == "BIlled":
        return "Billed", "normalized_from:BIlled"
    return text, None
