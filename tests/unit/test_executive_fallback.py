"""Tests for executive fallback formatting."""

from src.agent.executive_fallback import format_executive_fallback


def test_fallback_revenue_summary_no_json():
    text = format_executive_fallback([{
        "metric": "revenue_summary",
        "metrics": {
            "billed_revenue": {"value": 126_700_000},
            "collected_revenue": {"value": 90_400_000},
            "receivables": {"value": 36_300_000},
        },
    }])
    assert "₹126.7M" in text
    assert "json" not in text.lower()
    assert "maximum number of analysis steps" not in text.lower()
    assert "billed revenue" in text.lower()


def test_fallback_pipeline_analysis():
    text = format_executive_fallback([{
        "analysis": "pipeline",
        "sector": "Energy",
        "period": "Q3 2026",
        "open_deal_count": 3,
        "pipeline_inr": 5_000_000,
    }])
    assert "Energy" in text
    assert "Q3 2026" in text
    assert "3" in text


def test_fallback_empty():
    text = format_executive_fallback([])
    assert "couldn't complete" in text.lower()
