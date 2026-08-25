"""Unit tests for context budget and token efficiency."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from groq import APIStatusError

from config.settings import Settings
from src.agent.context_budget import (
    aggressively_compact_messages,
    compact_tool_result,
    estimate_tokens,
    trim_history,
    validate_context_budget,
)
from src.agent.groq_client import is_request_too_large
from src.agent.runner import AgentRunner


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_trim_history():
    history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    trimmed = trim_history(history, max_messages=6)
    assert len(trimmed) == 6
    assert trimmed[0]["content"] == "msg4"


def test_compact_query_no_records():
    result = compact_tool_result("query_items", {
        "board": "deals",
        "row_count": 347,
        "filters_applied": {},
        "note": "Summary only",
    })
    assert "records" not in result
    assert result["row_count"] == 347


def test_compact_query_truncates_records():
    records = [{"id": i, "value": i * 100} for i in range(50)]
    result = compact_tool_result("query_items", {
        "board": "deals",
        "row_count": 50,
        "records": records,
        "returned_count": 5,
    })
    assert len(result["records"]) <= 5


def test_compact_aggregate():
    groups = [{"sector": f"S{i}", "total": i} for i in range(30)]
    result = compact_tool_result("aggregate", {
        "metrics": {"total_ar": 1000},
        "groups": groups,
        "valid_row_count": 180,
    })
    assert len(result["groups"]) <= 20
    assert result["metrics"]["total_ar"] == 1000


def test_compact_join_strips_nested_data():
    companies = [{
        "company_code": "COMPANY001",
        "match_confidence": "normalized_exact",
        "deals": [{"deal_value": 1}] * 10,
        "work_orders": [{"amount_receivable": 2}] * 5,
        "total_ar": 100,
        "total_open_pipeline_value": 200,
    }]
    result = compact_tool_result("join_by_company", {
        "match_summary": {"matched": 1},
        "companies": companies,
        "unmatched": {"wo_only": [], "deal_only_count": 0},
    })
    assert "companies_sample" in result
    assert "deals" not in result["companies_sample"][0]


def test_compact_leadership():
    result = compact_tool_result("generate_leadership_snapshot", {
        "as_of": "2026-01-01",
        "sections": {
            "pipeline_headline": {"open_deal_count": 49, "raw_pipeline_value_inr": 1e8},
            "cash_collection": {"total_ar_inr": 3.6e7, "top_ar_companies": []},
            "operations": {"not_started": 10, "ongoing": 20},
            "cross_board_risks": {"stale_open_deals_count": 2},
            "data_quality": {"work_order_count": 180, "deal_count": 347},
            "pipeline_by_stage": {"groups": []},
        },
    })
    assert "pipeline" in result
    assert "sections" not in result


def test_validate_context_budget():
    messages = [{"role": "user", "content": "hello"}]
    ok, tokens = validate_context_budget(messages, max_tokens=6000)
    assert ok
    assert tokens > 0


def test_aggressively_compact_messages():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "old reply"},
        {"role": "user", "content": "new question"},
        {"role": "tool", "content": "x" * 5000, "tool_call_id": "1"},
    ]
    compacted = aggressively_compact_messages(messages)
    tool_msgs = [m for m in compacted if m["role"] == "tool"]
    assert len(tool_msgs[0]["content"]) <= 2100


def test_is_request_too_large():
    err = APIStatusError("Request too large", response=MagicMock(status_code=413), body=None)
    assert is_request_too_large(err) is True


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        GROQ_MODEL="openai/gpt-oss-120b",
    )


def test_kpi_question_single_tool_call():
    """Revenue question should use business_metric, not dump raw data."""
    with patch("src.agent.runner.create_data_service") as mock_ds:
        mock_ds.return_value = MagicMock()
        with patch("src.agent.runner.create_groq_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client_fn.return_value = mock_client

            from types import SimpleNamespace

            tool_call = SimpleNamespace(
                id="c1",
                function=SimpleNamespace(
                    name="business_metric",
                    arguments='{"metric": "total_revenue"}',
                ),
            )
            msg = SimpleNamespace(content=None, tool_calls=[tool_call])
            mock_client.chat.completions.create.side_effect = [
                SimpleNamespace(choices=[SimpleNamespace(message=msg)]),
                SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Revenue breakdown...", tool_calls=None),
                )]),
            ]

            agent = AgentRunner(settings=_settings())
            agent.client = mock_client

            compact_result = {
                "metric": "total_revenue",
                "breakdown": {
                    "billed_revenue": {"value": 100, "currency": "INR"},
                },
            }
            with patch.object(agent.tool_registry, "execute", return_value=compact_result) as mock_exec:
                result = agent.run("What is our revenue?")

            mock_exec.assert_called_once()
            assert mock_exec.call_args[0][0] == "business_metric"
            tool_content = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"][-1]["content"]
            parsed = json.loads(tool_content)
            assert "breakdown" in parsed
            assert "rows" not in parsed
            assert "Revenue" in result or "revenue" in result.lower()


def test_no_raw_dataset_in_tool_messages():
    """Tool messages sent to Groq must not contain full datasets."""
    large_records = [{"field_" + str(i): i for i in range(50)} for _ in range(200)]
    compact = compact_tool_result("query_items", {
        "board": "work_orders",
        "row_count": 200,
        "records": large_records,
    })
    serialized = json.dumps(compact)
    # Compact should not include 200 full records
    assert serialized.count('"field_') < 200 * 10
