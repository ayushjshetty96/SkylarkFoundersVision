"""Unit tests for tool call loop detection."""

from __future__ import annotations

from src.agent.tool_loop import ToolCallTracker, tool_call_signature


def test_tool_call_signature_stable():
    sig1 = tool_call_signature("business_metric", {"metric": "total_revenue"})
    sig2 = tool_call_signature("business_metric", {"metric": "total_revenue"})
    assert sig1 == sig2


def test_repeat_detection_returns_cached():
    tracker = ToolCallTracker()
    args = {"operation": "good_customers", "limit": 10}
    cached_result = {"operation": "good_customers", "customers": []}

    is_repeat, cached = tracker.check_repeat("customer_analysis", args)
    assert is_repeat is False
    assert cached is None

    tracker.store("customer_analysis", args, cached_result)

    is_repeat, cached = tracker.check_repeat("customer_analysis", args)
    assert is_repeat is True
    assert cached is not None
    assert cached["repeated_call"] is True


def test_different_args_not_repeat():
    tracker = ToolCallTracker()
    tracker.store("customer_analysis", {"operation": "good_customers"}, {"customers": []})
    is_repeat, _ = tracker.check_repeat("customer_analysis", {"operation": "customer_overview"})
    assert is_repeat is False
