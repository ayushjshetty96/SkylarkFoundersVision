"""Cross-board company join using normalized company codes only."""

from __future__ import annotations

from collections import defaultdict

from src.models.records import CompanyJoinResult, Deal, JoinByCompanyResult, JoinSummary, WorkOrder
from src.normalization.company_code import normalize_company_code


def join_by_company(
    deals: list[Deal],
    work_orders: list[WorkOrder],
    company_codes: list[str] | None = None,
) -> JoinByCompanyResult:
    wo_by_company: dict[str, list[WorkOrder]] = defaultdict(list)
    deal_by_company: dict[str, list[Deal]] = defaultdict(list)
    warnings: list[str] = [
        "Cross-board joins use normalized company codes only; Deal Name is not a join key.",
    ]

    for wo in work_orders:
        code = wo.company_code
        if code:
            wo_by_company[code].append(wo)
        else:
            warnings.append(f"Work order {wo.item_id} has no normalizable company code.")

    for deal in deals:
        code = deal.company_code
        if code:
            deal_by_company[code].append(deal)
        else:
            warnings.append(f"Deal {deal.item_id} has no normalizable company code.")

    all_wo_codes = set(wo_by_company.keys())
    all_deal_codes = set(deal_by_company.keys())

    if company_codes:
        target_codes = {normalize_company_code(c) for c in company_codes}
        target_codes.discard(None)
    else:
        target_codes = all_wo_codes | all_deal_codes

    summary = JoinSummary()
    companies: list[CompanyJoinResult] = []
    wo_only: list[str] = []
    deal_only: list[str] = []

    for code in sorted(target_codes):
        wos = wo_by_company.get(code, [])
        dls = deal_by_company.get(code, [])
        in_wo = code in all_wo_codes
        in_deals = code in all_deal_codes

        if in_wo and in_deals:
            summary.normalized_exact += 1
            confidence = "normalized_exact"
            method = "numeric_id_normalization"
        elif in_wo:
            summary.unmatched_wo_only += 1
            wo_only.append(code)
            confidence = "unmatched"
            method = "wo_only"
        elif in_deals:
            summary.unmatched_deal_only += 1
            deal_only.append(code)
            confidence = "unmatched"
            method = "deal_only"
        else:
            continue

        open_pipeline = sum(
            d.deal_value for d in dls
            if d.deal_status == "Open" and d.deal_value is not None
        ) or None

        total_ar = sum(
            w.amount_receivable for w in wos
            if w.amount_receivable is not None
        )
        if not wos:
            total_ar_val = None
        else:
            total_ar_val = total_ar

        contract_val = sum(
            w.contract_value_incl_gst for w in wos
            if w.contract_value_incl_gst is not None
        ) or None

        match_warnings: list[str] = []
        if confidence == "unmatched" and method == "wo_only":
            match_warnings.append(f"{code} has work orders but no deals.")
        if confidence == "unmatched" and method == "deal_only":
            match_warnings.append(f"{code} has deals but no work orders.")

        wo_sectors = {w.sector_normalized for w in wos if w.sector_normalized}
        deal_sectors = {d.sector_normalized for d in dls if d.sector_normalized}
        if wo_sectors and deal_sectors and wo_sectors != deal_sectors:
            match_warnings.append(
                f"{code}: sector mismatch WO={wo_sectors} vs Deals={deal_sectors}"
            )

        companies.append(
            CompanyJoinResult(
                company_code=code,
                match_confidence=confidence,
                match_method=method,
                deals=dls,
                work_orders=wos,
                match_warnings=match_warnings,
                total_open_pipeline_value=open_pipeline if dls else None,
                total_ar=total_ar_val,
                total_contract_value_wo=contract_val,
            )
        )

    sector_mismatch_count = sum(1 for c in companies if any("sector mismatch" in w for w in c.match_warnings))
    if sector_mismatch_count:
        warnings.append(f"{sector_mismatch_count} matched companies have sector label mismatches.")

    return JoinByCompanyResult(
        match_summary=summary,
        companies=companies,
        unmatched={
            "wo_only": wo_only,
            "deal_only": deal_only,
            "deal_only_count": len(deal_only),
        },
        warnings=warnings,
    )
