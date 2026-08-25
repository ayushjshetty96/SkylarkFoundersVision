"""Executive data integrity summary — messy data made visible without noise."""

from __future__ import annotations

from typing import Any

from src.dashboard.data import CachedMondayData
from src.dashboard.metrics import DashboardMetrics
from src.models.records import Deal, WorkOrder


def _wo_has_parse_issue(wo: WorkOrder) -> bool:
    return any("parse_failed" in w for w in wo.field_warnings)


def _deal_has_parse_issue(deal: Deal) -> bool:
    return any("parse_failed" in w for w in deal.field_warnings)


def _wo_complete(wo: WorkOrder) -> bool:
    if not wo.company_code:
        return False
    if _wo_has_parse_issue(wo):
        return False
    return True


def _deal_complete(deal: Deal) -> bool:
    if not deal.company_code:
        return False
    if _deal_has_parse_issue(deal):
        return False
    return True


def _deal_missing_date(deal: Deal) -> bool:
    return not deal.tentative_close_date and not deal.close_date and not deal.created_date


def compute_data_integrity(data: CachedMondayData, metrics: DashboardMetrics) -> dict[str, Any]:
    """Compact executive data-quality summary from live normalized records."""
    wos = data.work_orders
    deals = data.deals
    dq = metrics.data_quality

    records_analyzed = len(wos) + len(deals)
    wo_complete = sum(1 for w in wos if _wo_complete(w))
    deal_complete = sum(1 for d in deals if _deal_complete(d))
    complete_records = wo_complete + deal_complete
    incomplete_records = records_analyzed - complete_records

    parse_issues = sum(1 for w in wos if _wo_has_parse_issue(w)) + sum(
        1 for d in deals if _deal_has_parse_issue(d)
    )
    missing_collections = sum(
        1 for w in wos if w.collected_amount_incl_gst is None and (w.billed_value_incl_gst or 0) > 0
    )
    missing_deal_dates = sum(1 for d in deals if _deal_missing_date(d))
    missing_deal_values = dq.get("missing_deal_values") or sum(1 for d in deals if d.deal_value is None)
    missing_company_codes = sum(1 for w in wos if not w.company_code) + sum(
        1 for d in deals if not d.company_code
    )

    open_deals = [d for d in deals if d.deal_status == "Open"]
    open_no_close_date = sum(1 for d in open_deals if _deal_missing_date(d))

    wo_only = dq.get("wo_only_companies")
    if isinstance(wo_only, list):
        wo_only_count = len(wo_only)
    else:
        wo_only_count = dq.get("wo_only_company_count") or 0

    deal_only = dq.get("deal_only_company_count") or 0
    cross_board_matches = dq.get("matched_companies") or 0
    sector_mismatches = dq.get("sector_mismatch_companies") or 0
    unmatched = wo_only_count + deal_only

    issue_score = 0
    if records_analyzed:
        issue_score += (incomplete_records / records_analyzed) * 40
    issue_score += min(parse_issues * 2, 20)
    issue_score += min(missing_collections / max(len(wos), 1) * 30, 25)
    issue_score += min(sector_mismatches, 15)

    if issue_score < 15:
        confidence = "HIGH"
    elif issue_score < 35:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    reasons: list[str] = []
    if missing_collections > 0:
        reasons.append(f"{missing_collections} work orders have missing collection values.")
    if parse_issues > 0:
        reasons.append(f"{parse_issues} records contain parse issues.")
    if sector_mismatches > 0:
        reasons.append(f"{sector_mismatches} cross-board sector mismatches.")
    if missing_deal_values > 0:
        reasons.append(f"{missing_deal_values} deals missing financial values.")
    if open_no_close_date > 0:
        reasons.append(f"{open_no_close_date} open deals have no usable close date.")

    caveats: dict[str, str] = {}
    if missing_collections > 0:
        caveats["receivables"] = f"{missing_collections} records have missing collection values"
        caveats["collection_rate"] = f"{missing_collections} records have missing collection values"
    if missing_deal_values > 0:
        caveats["pipeline"] = f"{missing_deal_values} deals excluded from pipeline sums (missing values)"
    if open_no_close_date > 0:
        caveats["pipeline_period"] = f"{open_no_close_date} open deals have no close date for period filters"

    diagnostics: list[dict[str, Any]] = []
    if parse_issues:
        diagnostics.append({"issue": "Parse failures", "count": parse_issues})
    if missing_collections:
        diagnostics.append({"issue": "Missing collection values", "count": missing_collections})
    if missing_deal_dates:
        diagnostics.append({"issue": "Missing deal dates", "count": missing_deal_dates})
    if missing_company_codes:
        diagnostics.append({"issue": "Missing company codes", "count": missing_company_codes})
    if sector_mismatches:
        diagnostics.append({"issue": "Sector mismatches", "count": sector_mismatches})
    if wo_only_count:
        diagnostics.append({"issue": "WO-only companies", "count": wo_only_count})
    if deal_only:
        diagnostics.append({"issue": "Deal-only companies", "count": deal_only})

    return {
        "records_analyzed": records_analyzed,
        "work_orders": len(wos),
        "deals": len(deals),
        "complete_records": complete_records,
        "incomplete_records": incomplete_records,
        "parse_issues": parse_issues,
        "missing_collections": missing_collections,
        "missing_deal_dates": missing_deal_dates,
        "missing_deal_values": missing_deal_values,
        "missing_company_codes": missing_company_codes,
        "open_deals_no_close_date": open_no_close_date,
        "cross_board_matches": cross_board_matches,
        "unmatched_companies": unmatched,
        "sector_mismatches": sector_mismatches,
        "confidence": confidence,
        "confidence_reasons": reasons[:5],
        "caveats": caveats,
        "diagnostics": diagnostics,
        "live_snapshot_note": "Live snapshot — historical trend unavailable.",
    }
