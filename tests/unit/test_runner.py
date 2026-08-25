"""Unit tests for Groq agent runner (mocked, no live API)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from src.agent.runner import AgentRunner, GroqAgentError
from src.agent.tool_registry import parse_tool_arguments


def _settings() -> Settings:
    return Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test",
        GROQ_MODEL="openai/gpt-oss-120b",
    )


def _choice(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(message=message)


def _tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.fixture
def mock_agent():
    with patch("src.agent.runner.create_data_service") as mock_ds:
        mock_ds.return_value = MagicMock()
        with patch("src.agent.runner.create_groq_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client_fn.return_value = mock_client
            agent = AgentRunner(settings=_settings())
            agent.client = mock_client
            yield agent, mock_client


def test_plain_response(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[_choice(content="Pipeline is ₹100.")]
    )
    result = agent.run("What is pipeline?")
    assert "Pipeline" in result
    assert client.chat.completions.create.call_count == 1


def test_successful_tool_call(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("call_1", "get_board_schema", '{"board": "deals"}')],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="Deals board has 11 columns.")]),
    ]
    with patch.object(agent.tool_registry, "execute", return_value={"column_count": 11}) as mock_exec:
        result = agent.run("What columns are on deals?")
    assert "11 columns" in result
    mock_exec.assert_called_once_with("get_board_schema", {"board": "deals"})
    assert client.chat.completions.create.call_count == 2
    # Verify tool message includes tool_call_id
    second_call_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "call_1"


def test_multiple_tool_rounds(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c1", "business_metric", '{"metric": "open_deal_count"}')],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="There are 49 open deals.")]),
    ]
    with patch.object(agent.tool_registry, "execute", return_value={"metric": "open_deal_count", "value": 49}):
        result = agent.run("How many open deals?")
    assert "49" in result
    assert client.chat.completions.create.call_count == 2


def test_malformed_tool_arguments(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c1", "query_items", "not-valid-json")],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="I could not parse tool arguments.")]),
    ]
    with patch.object(agent.tool_registry, "execute") as mock_exec:
        result = agent.run("test")
    mock_exec.assert_not_called()
    assert client.chat.completions.create.call_count == 2


def test_unknown_tool_returns_error_to_model(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c1", "nonexistent_tool", "{}")],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="Unknown tool handled.")]),
    ]
    result = agent.run("test")
    assert "handled" in result


def test_groq_401_raises_classified_error(mock_agent):
    agent, client = mock_agent
    from groq import APIStatusError

    err = APIStatusError("Unauthorized", response=MagicMock(status_code=401), body=None)
    client.chat.completions.create.side_effect = err
    with pytest.raises(GroqAgentError, match="authentication"):
        agent.run("hello")


def test_parse_tool_arguments_json_string():
    args, err = parse_tool_arguments('{"board": "deals"}')
    assert err is None
    assert args == {"board": "deals"}


def test_parse_tool_arguments_dict():
    args, err = parse_tool_arguments({"board": "deals"})
    assert err is None
    assert args["board"] == "deals"


def test_repeated_tool_call_uses_cache(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c1", "business_metric", '{"metric": "total_revenue"}')],
            )]
        ),
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c2", "business_metric", '{"metric": "total_revenue"}')],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="Revenue summary provided.")]),
    ]
    with patch.object(agent.tool_registry, "execute", return_value={"metric": "revenue_summary", "do_not_sum": True}) as mock_exec:
        result = agent.run("What is revenue?")
    assert mock_exec.call_count == 1
    assert "summary" in result.lower() or "Revenue" in result


def test_customer_analysis_tool_call(mock_agent):
    agent, client = mock_agent
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[_choice(
                tool_calls=[_tool_call("c1", "customer_analysis", '{"operation": "good_customers"}')],
            )]
        ),
        SimpleNamespace(choices=[_choice(content="COMPANY001 is a strong customer.")]),
    ]
    with patch.object(
        agent.tool_registry,
        "execute",
        return_value={"operation": "good_customers", "customers": [{"company_code": "COMPANY001"}]},
    ) as mock_exec:
        result = agent.run("Who is a good customer?")
    mock_exec.assert_called_once_with("customer_analysis", {"operation": "good_customers"})
    assert client.chat.completions.create.call_count == 2
    assert "COMPANY001" in result or "customer" in result.lower()


def test_413_compact_retry(mock_agent):
    agent, client = mock_agent
    from groq import APIStatusError

    err = APIStatusError("Request too large", response=MagicMock(status_code=413), body=None)
    client.chat.completions.create.side_effect = [
        err,
        SimpleNamespace(choices=[_choice(content="Compacted and answered.")]),
    ]
    result = agent.run("What is revenue?")
    assert "answered" in result.lower() or "Compacted" in result
    assert client.chat.completions.create.call_count == 2


def test_parse_tool_arguments_malformed():
    args, err = parse_tool_arguments("{bad json")
    assert err is not None
    assert args == {}
