"""Deterministic pipeline analysis with sector and date-period filters."""

from __future__ import annotations

from datetime import date
from typing import Any

from config.settings import Settings, get_settings
from src.data_service import DataService
from src.models.records import Deal
from src.normalization.date_ranges import DateRange, date_in_range, resolve_period
from src.normalization.sectors import normalize_sector_query, sector_matches
from src.tools.aggregate import aggregate, weighted_pipeline_sum

# For open pipeline timing we prefer expected close, then actual close, then created.
DATE_FIELD_PRIORITY = ("tentative_close_date", "close_date", "created_date")
DEFAULT_DATE_FIELD = "tentative_close_date"


def _parse_deal_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def deal_reference_date(deal: dict[str, Any], preferred_field: str | None = None) -> tuple[date | None, str]:
    """Return (date, field_used) using fallback chain."""
    fields: tuple[str, ...]
    if preferred_field and preferred_field in DATE_FIELD_PRIORITY:
        fields = (preferred_field,) + tuple(f for f in DATE_FIELD_PRIORITY if f != preferred_field)
    else:
        fields = DATE_FIELD_PRIORITY

    for field in fields:
        parsed = _parse_deal_date(deal.get(field))
        if parsed is not None:
            return parsed, field
    return None, fields[0]


def filter_open_deals(
    deals: list[dict[str, Any]],
    *,
    sector: str | None = None,
    period: DateRange | None = None,
    date_field: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter open deals by sector and/or date period."""
    sector_query = normalize_sector_query(sector) if sector else None
    matched: list[dict[str, Any]] = []
    excluded_no_date = 0
    excluded_out_of_period = 0
    excluded_sector = 0
    fields_used: dict[str, int] = {}

    for deal in deals:
        if deal.get("deal_status") != "Open":
            continue

        record_sector = deal.get("sector_normalized") or deal.get("sector")
        if sector_query and not sector_matches(record_sector, sector_query):
            excluded_sector += 1
            continue

        if period:
            ref_date, field_used = deal_reference_date(deal, date_field)
            fields_used[field_used] = fields_used.get(field_used, 0) + 1
            if ref_date is None:
                excluded_no_date += 1
                continue
            if not date_in_range(ref_date, period):
                excluded_out_of_period += 1
                continue

        matched.append(deal)

    meta = {
        "sector_filter": sector_query,
        "period": period.label if period else None,
        "period_start": period.start.isoformat() if period else None,
        "period_end": period.end.isoformat() if period else None,
        "date_field_priority": list(DATE_FIELD_PRIORITY),
        "date_field_note": (
            "Open pipeline period filtering uses tentative_close_date when available, "
            "then close_date, then created_date."
        ),
        "excluded_no_reference_date": excluded_no_date,
        "excluded_out_of_period": excluded_out_of_period,
        "excluded_sector_mismatch": excluded_sector,
        "date_fields_used": fields_used,
    }
    return matched, meta


def pipeline_analysis_tool(
    data_service: DataService,
    *,
    sector: str | None = None,
    period: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    date_field: str | None = None,
    settings: Settings | None = None,
    work_orders: list | None = None,
    deals: list | None = None,
) -> dict[str, Any]:
    """Compact filtered pipeline analysis — sector and/or time period."""
    settings = settings or get_settings()
    if deals is None:
        deals = data_service.get_deals()
    deal_dicts = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in deals]

    explicit_start = _parse_deal_date(period_start) if period_start else None
    explicit_end = _parse_deal_date(period_end) if period_end else None
    date_range = resolve_period(period, start=explicit_start, end=explicit_end)

    filtered, filter_meta = filter_open_deals(
        deal_dicts,
        sector=sector,
        period=date_range,
        date_field=date_field,
    )

    weights = {
        "High": settings.prob_weight_high,
        "Medium": settings.prob_weight_medium,
        "Low": settings.prob_weight_low,
    }
    pipeline = weighted_pipeline_sum(filtered, weights=weights)

    stage_agg = aggregate(
        filtered,
        group_by=["deal_stage"],
        metrics=[
            {"name": "deal_count", "field": "*", "op": "count"},
            {"name": "pipeline_value", "field": "deal_value", "op": "sum"},
        ],
    )

    total_open = sum(1 for d in deal_dicts if d.get("deal_status") == "Open")
    caveats: list[str] = []
    if filter_meta.get("excluded_no_reference_date"):
        caveats.append(
            f"{filter_meta['excluded_no_reference_date']} open deals excluded — no close/created date for period filter."
        )
    if pipeline.get("missing_value_count"):
        caveats.append(
            f"{pipeline['missing_value_count']} deals excluded from pipeline value sums due to missing deal values."
        )
    if date_range and filter_meta.get("excluded_out_of_period"):
        caveats.append(
            f"{filter_meta['excluded_out_of_period']} open deals fell outside {date_range.label}."
        )

    return {
        "analysis": "pipeline",
        "sector": filter_meta.get("sector_filter"),
        "period": filter_meta.get("period"),
        "period_start": filter_meta.get("period_start"),
        "period_end": filter_meta.get("period_end"),
        "date_field_note": filter_meta.get("date_field_note"),
        "open_deal_count": pipeline.get("open_deal_count"),
        "open_deal_count_total_board": total_open,
        "pipeline_inr": pipeline.get("raw_pipeline_value"),
        "weighted_pipeline_inr": pipeline.get("weighted_pipeline_value"),
        "stages": (stage_agg.groups or [])[:10],
        "missing_deal_value_count": pipeline.get("missing_value_count"),
        "filter_meta": filter_meta,
        "data_quality_caveats": caveats,
        "currency": "INR",
        "record_count_normalized_deals": len(deal_dicts),
    }
