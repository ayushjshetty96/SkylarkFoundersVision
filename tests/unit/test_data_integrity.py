"""Tests for data integrity executive summary."""

from __future__ import annotations

from datetime import datetime, timezone

from src.dashboard.data import CachedMondayData
from src.dashboard.data_integrity import compute_data_integrity
from src.dashboard.metrics import DashboardMetrics
from src.models.deal import Deal
from src.models.work_order import WorkOrder


def _sample_bundle():
    wos = [
        WorkOrder(item_id="w1", company_code="COMPANY001", billed_value_incl_gst=100_000),
        WorkOrder(item_id="w2", company_code=None),
        WorkOrder(
            item_id="w3",
            company_code="COMPANY002",
            billed_value_incl_gst=50_000,
            collected_amount_incl_gst=None,
        ),
    ]
    wos[2].field_warnings.append("collected_amount_incl_gst:parse_failed")
    deals = [
        Deal(item_id="d1", company_code="COMPANY001", deal_status="Open"),
        Deal(item_id="d2", company_code="COMPANY003", deal_status="Open", deal_value=None),
    ]
    data = CachedMondayData(
        work_orders=wos,
        deals=deals,
        loaded_at=datetime.now(timezone.utc),
        work_order_count=3,
        deal_count=2,
    )
    metrics = DashboardMetrics(
        revenue={},
        pipeline={},
        operations={},
        customers={"rows": []},
        sectors={},
        data_quality={
            "matched_companies": 1,
            "sector_mismatch_companies": 2,
            "wo_only_company_count": 1,
            "deal_only_company_count": 1,
            "missing_deal_values": 1,
        },
    )
    return data, metrics


def test_data_integrity_summary_fields():
    data, metrics = _sample_bundle()
    dq = compute_data_integrity(data, metrics)
    assert dq["records_analyzed"] == 5
    assert dq["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert "missing_collections" in dq
    assert dq["missing_collections"] >= 1
    assert dq["live_snapshot_note"] == "Live snapshot — historical trend unavailable."


def test_data_integrity_caveats_for_receivables():
    data, metrics = _sample_bundle()
    dq = compute_data_integrity(data, metrics)
    if dq["missing_collections"] > 0:
        assert "receivables" in dq["caveats"] or "collection_rate" in dq["caveats"]


def test_data_integrity_diagnostics_not_empty_when_issues():
    data, metrics = _sample_bundle()
    dq = compute_data_integrity(data, metrics)
    assert len(dq["diagnostics"]) > 0


def test_data_confidence_reasons():
    data, metrics = _sample_bundle()
    dq = compute_data_integrity(data, metrics)
    assert isinstance(dq["confidence_reasons"], list)
