"""Deterministic executive intelligence engine — no LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.dashboard.customer_tiers import classify_customer_tier, customer_concentration
from src.dashboard.data import CachedMondayData
from src.dashboard.data_integrity import compute_data_integrity
from src.dashboard.health import calculate_health_score, classify_customer_health
from src.dashboard.metrics import DashboardMetrics
from src.dashboard.pipeline_radar import build_pipeline_radar
from src.tools.pipeline_analysis import pipeline_analysis_tool
from src.ui.formatting import fmt_customer_code


@dataclass
class IntelligenceBundle:
    health: dict[str, Any] = field(default_factory=dict)
    risks: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    this_week: list[dict[str, Any]] = field(default_factory=list)
    founder_actions: list[dict[str, Any]] = field(default_factory=list)
    insights: list[dict[str, Any]] = field(default_factory=list)
    pipeline_radar: dict[str, Any] = field(default_factory=dict)
    revenue_gaps: dict[str, Any] = field(default_factory=dict)
    customer_concentration: dict[str, Any] = field(default_factory=dict)
    sector_ranking: list[dict[str, Any]] = field(default_factory=list)
    operations_risks: list[dict[str, Any]] = field(default_factory=list)
    cross_board: list[dict[str, Any]] = field(default_factory=list)
    data_integrity: dict[str, Any] = field(default_factory=dict)
    risks_by_category: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    opportunities_by_category: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _insight(
    *,
    title: str,
    severity: str,
    metric: str,
    explanation: str,
    action: str,
    category: str = "insight",
    risk_type: str | None = None,
    opportunity_type: str | None = None,
    what: str | None = None,
    why: str | None = None,
    value: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "severity": severity,
        "metric": metric,
        "explanation": explanation,
        "action": action,
        "category": category,
        "risk_type": risk_type,
        "opportunity_type": opportunity_type,
        "what": what or title,
        "why": why or explanation,
        "value": value or metric,
    }


def _fmt_inr_short(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1_000_000:
        return f"₹{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"₹{value / 1_000:.0f}K"
    return f"₹{value:,.0f}"


def compute_revenue_gaps(rev: dict[str, Any]) -> dict[str, Any]:
    contract = rev.get("contract_value") or 0
    billed = rev.get("billed_revenue") or 0
    collected = rev.get("collected_revenue") or 0
    receivables = rev.get("receivables") or 0
    return {
        "contract_value": contract,
        "billed_revenue": billed,
        "collected_revenue": collected,
        "receivables": receivables,
        "unbilled_gap": max(contract - billed, 0) if contract and billed else None,
        "uncollected_from_billed": max(billed - collected, 0) if billed and collected else None,
        "collection_rate": rev.get("collection_rate"),
        "billing_rate": rev.get("billing_rate"),
    }


def build_founder_actions(
    metrics: DashboardMetrics,
    intel_ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ranked founder priorities — deterministic."""
    actions: list[dict[str, Any]] = []
    rev = metrics.revenue
    pipe = metrics.pipeline
    rows = intel_ctx.get("rows") or []
    dq = intel_ctx.get("data_integrity") or {}

    ar = rev.get("receivables") or 0
    if ar > 0:
        actions.append({
            "rank": 0,
            "category": "COLLECTION",
            "title": "COLLECTION",
            "detail": f"{_fmt_inr_short(ar)} receivables outstanding",
            "impact_score": ar,
            "urgency": "HIGH",
        })

    top_ar_customer = max(rows, key=lambda r: r.get("receivables") or 0, default=None)
    if top_ar_customer and (top_ar_customer.get("receivables") or 0) > 0:
        actions.append({
            "rank": 0,
            "category": "CUSTOMER",
            "title": "CUSTOMER",
            "detail": (
                f"{top_ar_customer.get('company_code')} — "
                f"{_fmt_inr_short(top_ar_customer.get('receivables'))} receivable"
            ),
            "impact_score": top_ar_customer.get("receivables") or 0,
            "urgency": "HIGH" if classify_customer_health(top_ar_customer) == "AT RISK" else "MEDIUM",
        })

    stale = pipe.get("stale_open_deals") or 0
    if stale > 0:
        actions.append({
            "rank": 0,
            "category": "PIPELINE",
            "title": "PIPELINE",
            "detail": f"{stale} stale opportunities require follow-up",
            "impact_score": stale * 1_000_000,
            "urgency": "MEDIUM",
        })

    stuck = metrics.operations.get("stuck") or 0
    if stuck > 0:
        actions.append({
            "rank": 0,
            "category": "OPERATIONS",
            "title": "OPERATIONS",
            "detail": f"{stuck} delayed/stuck work orders",
            "impact_score": stuck * 500_000,
            "urgency": "HIGH",
        })

    missing_coll = dq.get("missing_collections") or 0
    if missing_coll > 0:
        actions.append({
            "rank": 0,
            "category": "DATA",
            "title": "DATA",
            "detail": f"{missing_coll} missing collection values affecting cash visibility",
            "impact_score": missing_coll * 100_000,
            "urgency": "LOW",
        })

    actions.sort(key=lambda a: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[a["urgency"]], -a["impact_score"]))
    for i, a in enumerate(actions[:5], start=1):
        a["rank"] = i
    return actions[:5]


def _categorize_risks(risks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cats: dict[str, list[dict[str, Any]]] = {
        "CASH_RISK": [],
        "CUSTOMER_RISK": [],
        "PIPELINE_RISK": [],
        "OPERATIONAL_RISK": [],
        "DATA_RISK": [],
    }
    for r in risks:
        rt = r.get("risk_type") or "DATA_RISK"
        if rt in cats:
            cats[rt].append(r)
    return cats


def _categorize_opportunities(opps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cats: dict[str, list[dict[str, Any]]] = {
        "LARGE_PIPELINE": [],
        "LARGE_CUSTOMERS": [],
        "HIGH_VALUE_DEALS": [],
        "SECTOR_OPPORTUNITIES": [],
        "CROSS_SELL": [],
    }
    for o in opps:
        ot = o.get("opportunity_type") or "SECTOR_OPPORTUNITIES"
        key = ot if ot in cats else "SECTOR_OPPORTUNITIES"
        cats[key].append(o)
    return cats


def build_sector_ranking(metrics: DashboardMetrics) -> list[dict[str, Any]]:
    sectors: dict[str, dict[str, Any]] = {}
    for row in metrics.sectors.get("by_pipeline", []):
        name = row.get("sector_normalized") or "Unknown"
        sectors.setdefault(name, {"sector": name})
        sectors[name]["pipeline"] = row.get("pipeline")
    for row in metrics.sectors.get("by_contract_value", []):
        name = row.get("sector_normalized") or "Unknown"
        sectors.setdefault(name, {"sector": name})
        sectors[name]["contract_value"] = row.get("contract_value")
    for row in metrics.sectors.get("by_work_orders", []):
        name = row.get("sector_normalized") or "Unknown"
        sectors.setdefault(name, {"sector": name})
        sectors[name]["work_orders"] = row.get("wo_count")

    ranked = sorted(
        sectors.values(),
        key=lambda s: (s.get("pipeline") or 0) + (s.get("contract_value") or 0) * 0.1,
        reverse=True,
    )
    for i, s in enumerate(ranked[:10]):
        s["rank"] = i + 1
        pipe = s.get("pipeline") or 0
        contract = s.get("contract_value") or 0
        s["momentum"] = "STRONG" if pipe > 0 and contract > 0 else ("PIPELINE" if pipe > 0 else "EXECUTION")
    return ranked[:10]


def detect_operations_risks(data: CachedMondayData, metrics: DashboardMetrics) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    today = date.today()

    for wo in data.work_orders:
        status = (wo.execution_status or "").lower()
        billing = (wo.billing_status or "").lower()
        if "stuck" in status or "paused" in status:
            risks.append({
                "type": "stuck_work",
                "item_id": wo.item_id,
                "company_code": wo.company_code,
                "detail": wo.execution_status,
            })
        if status == "completed" and billing and billing not in ("billed", "paid", "done"):
            risks.append({
                "type": "completed_unbilled",
                "item_id": wo.item_id,
                "company_code": wo.company_code,
                "detail": wo.billing_status,
            })
        if wo.end_date and wo.end_date < today and status not in ("completed", "done"):
            risks.append({
                "type": "overdue_work",
                "item_id": wo.item_id,
                "company_code": wo.company_code,
                "detail": str(wo.end_date),
            })
        if wo.quantity_po and wo.quantity_billed:
            po_v = wo.quantity_po.value
            billed_v = wo.quantity_billed.value
            if po_v and billed_v and billed_v > po_v * 1.05:
                risks.append({
                    "type": "quantity_mismatch",
                    "item_id": wo.item_id,
                    "company_code": wo.company_code,
                })

    ops = metrics.operations
    if (ops.get("stuck") or 0) > 0:
        risks.append({"type": "summary", "detail": f"{ops['stuck']} work orders stuck/paused"})
    return risks[:20]


def build_intelligence(
    data: CachedMondayData,
    metrics: DashboardMetrics,
) -> IntelligenceBundle:
    """Compute full intelligence bundle from cached data + metrics."""
    health = calculate_health_score(metrics)
    rev = metrics.revenue
    pipe = metrics.pipeline
    rows = metrics.customers.get("rows") or []
    open_deals = [
        d.model_dump(mode="json") for d in data.deals if d.deal_status == "Open"
    ]

    radar = build_pipeline_radar(open_deals)
    gaps = compute_revenue_gaps(rev)
    concentration = customer_concentration(rows)
    sector_ranking = build_sector_ranking(metrics)
    ops_risks = detect_operations_risks(data, metrics)
    data_integrity = compute_data_integrity(data, metrics)

    risks: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []

    ar = rev.get("receivables") or 0
    if ar >= 1_000_000:
        top_ar = sorted(rows, key=lambda r: r.get("receivables") or 0, reverse=True)[:4]
        ar_sum = sum(r.get("receivables") or 0 for r in top_ar)
        risks.append(_insight(
            title="HIGH RECEIVABLE CONCENTRATION",
            severity="HIGH",
            metric=_fmt_inr_short(ar_sum),
            explanation=f"{_fmt_inr_short(ar)} total receivables; top accounts hold significant exposure.",
            action="Prioritize collections from the largest outstanding accounts.",
            category="risk",
            risk_type="CASH_RISK",
        ))

    stale = pipe.get("stale_open_deals") or 0
    if stale > 0:
        risks.append(_insight(
            title="STALE OPEN DEALS",
            severity="MEDIUM",
            metric=str(stale),
            explanation=f"{stale} open deals have passed tentative close dates.",
            action="Review stale pipeline and update close dates or close out deals.",
            category="risk",
            risk_type="PIPELINE_RISK",
        ))

    stuck = metrics.operations.get("stuck") or 0
    if stuck > 0:
        risks.append(_insight(
            title="STUCK WORK ORDERS",
            severity="HIGH",
            metric=str(stuck),
            explanation=f"{stuck} work orders are stuck or paused.",
            action="Unblock execution on stuck work orders this week.",
            category="risk",
            risk_type="OPERATIONAL_RISK",
        ))

    missing = pipe.get("missing_deal_value_count") or 0
    if missing > 0:
        risks.append(_insight(
            title="MISSING DEAL VALUES",
            severity="LOW",
            metric=str(missing),
            explanation=f"{missing} deals excluded from pipeline sums due to missing values.",
            action="Complete deal values in Monday for accurate pipeline reporting.",
            category="data_quality",
            risk_type="DATA_RISK",
        ))

    missing_coll = data_integrity.get("missing_collections") or 0
    if missing_coll > 0:
        risks.append(_insight(
            title="MISSING COLLECTION DATA",
            severity="MEDIUM",
            metric=str(missing_coll),
            explanation=f"{missing_coll} work orders lack collection values — cash visibility is incomplete.",
            action="Complete collection fields on billed work orders.",
            category="data_quality",
            risk_type="DATA_RISK",
        ))

    at_risk_customers = [r for r in rows if classify_customer_health(r) == "AT RISK"]
    for cust in sorted(at_risk_customers, key=lambda r: r.get("receivables") or 0, reverse=True)[:3]:
        code = cust.get("company_code") or "Unknown"
        risks.append(_insight(
            title=f"CUSTOMER AT RISK — {code}",
            severity="HIGH",
            metric=_fmt_inr_short(cust.get("receivables")),
            explanation=f"{code} flagged AT RISK with outstanding receivables.",
            action=f"Follow up on collections for {code} before expanding exposure.",
            category="risk",
            risk_type="CUSTOMER_RISK",
        ))

    high_value = radar.get("buckets", {}).get("HIGH VALUE", [])
    if high_value:
        opportunities.append(_insight(
            title="HIGH VALUE PIPELINE",
            severity="OPPORTUNITY",
            metric=_fmt_inr_short(high_value[0].get("deal_value")),
            explanation=f"{len(high_value)} high-value open deal(s) in pipeline.",
            action="Focus leadership attention on advancing the largest opportunities.",
            category="opportunity",
            opportunity_type="HIGH_VALUE_DEALS",
        ))

    quick_wins = radar.get("buckets", {}).get("QUICK WIN", [])
    if quick_wins:
        opportunities.append(_insight(
            title="QUICK WIN DEALS",
            severity="OPPORTUNITY",
            metric=str(len(quick_wins)),
            explanation="Deals with high closure probability and meaningful value.",
            action="Accelerate close on quick-win opportunities this month.",
            category="opportunity",
            opportunity_type="HIGH_VALUE_DEALS",
        ))

    if sector_ranking:
        top_sector = sector_ranking[0]
        pipe_val = top_sector.get("pipeline") or 0
        opportunities.append(_insight(
            title="STRONGEST SECTOR",
            severity="OPPORTUNITY",
            metric=top_sector.get("sector", "—"),
            explanation=f"Leading sector by pipeline ({_fmt_inr_short(pipe_val)}) and execution activity.",
            action=f"Double down on {top_sector.get('sector')} sector momentum.",
            category="opportunity",
            opportunity_type="SECTOR_OPPORTUNITIES",
        ))

    if rows:
        top_cust = max(rows, key=lambda r: r.get("collected") or 0)
        opportunities.append(_insight(
            title="TOP CUSTOMER",
            severity="OPPORTUNITY",
            metric=fmt_customer_code(top_cust.get("company_code")),
            explanation=f"Highest collected revenue at {_fmt_inr_short(top_cust.get('collected'))}.",
            action="Deepen relationship and explore cross-sell opportunities.",
            category="opportunity",
            opportunity_type="LARGE_CUSTOMERS",
        ))

    share = concentration.get("share_pct")
    if share and share >= 50:
        risks.append(_insight(
            title="CUSTOMER CONCENTRATION",
            severity="MEDIUM",
            metric=f"{share}%",
            explanation=f"Top {concentration.get('top_n')} customers represent {share}% of collected revenue.",
            action="Diversify customer base and monitor concentration risk.",
            category="risk",
            risk_type="CUSTOMER_RISK",
        ))

    insights.extend(risks)
    insights.extend(opportunities)

    this_week: list[dict[str, Any]] = []
    founder_ctx = {"rows": rows, "data_integrity": data_integrity}
    founder_actions = build_founder_actions(metrics, founder_ctx)

    for action in founder_actions[:5]:
        this_week.append({
            "priority": action["rank"],
            "action": action["detail"],
            "source": action["category"],
        })

    cross_board = sorted(rows, key=lambda r: r.get("collected") or 0, reverse=True)[:10]
    for row in cross_board:
        row["tier"] = classify_customer_tier(row)
        row["health"] = classify_customer_health(row)

    return IntelligenceBundle(
        health=health,
        risks=risks,
        opportunities=opportunities,
        this_week=this_week,
        founder_actions=founder_actions,
        insights=insights,
        pipeline_radar=radar,
        revenue_gaps=gaps,
        customer_concentration=concentration,
        sector_ranking=sector_ranking,
        operations_risks=ops_risks,
        cross_board=cross_board,
        data_integrity=data_integrity,
        risks_by_category=_categorize_risks(risks),
        opportunities_by_category=_categorize_opportunities(opportunities),
    )


def filtered_pipeline_for_period(
    data_service,
    metrics: DashboardMetrics,
    *,
    sector: str | None = None,
    period: str = "this_quarter",
    settings=None,
) -> dict[str, Any]:
    """Wrapper for tab-level period/sector pipeline filter."""
    return pipeline_analysis_tool(
        data_service,
        sector=sector,
        period=period,
        settings=settings,
        work_orders=None,
        deals=None,
    )
