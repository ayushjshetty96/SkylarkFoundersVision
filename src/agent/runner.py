"""Agent runner with Groq OpenAI-compatible tool-calling loop."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from groq import APIStatusError

from config.settings import Settings, get_settings
from src.agent.context_budget import (
    aggressively_compact_messages,
    compact_tool_result,
    estimate_messages_tokens,
    estimate_tools_tokens,
    log_request_diagnostics,
    trim_history,
    validate_context_budget,
)
from src.agent.executive_fallback import format_executive_fallback
from src.agent.groq_client import (
    chat_completion,
    create_groq_client,
    format_groq_error_for_user,
    is_request_too_large,
)
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tool_loop import ToolCallTracker
from src.agent.tool_registry import ToolRegistry, parse_tool_arguments
from src.data_service import DataService, create_data_service

logger = logging.getLogger(__name__)
DEBUG_AGENT = os.getenv("DEBUG_AGENT_LOOP", "").lower() in ("1", "true", "yes")


class AgentRunner:
    def __init__(
        self,
        data_service: DataService | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.data_service = data_service or create_data_service(self.settings)
        self.tool_registry = ToolRegistry(self.data_service, self.settings)
        self.client = create_groq_client(self.settings)
        self.tool_trace: list[dict[str, Any]] = []
        self.last_request_tokens: int = 0

    def run(self, user_message: str, history: list[dict[str, str]] | None = None) -> str:
        history = trim_history(history or [], max_messages=self.settings.max_history_messages)
        self.tool_trace = []

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        tools = self.tool_registry.get_tools()

        try:
            return self._run_tool_loop(messages, tools)
        except APIStatusError as exc:
            logger.error("Groq API error: %s", type(exc).__name__)
            raise GroqAgentError(format_groq_error_for_user(exc)) from exc
        except Exception as exc:
            logger.error("Groq error: %s", type(exc).__name__)
            raise GroqAgentError(format_groq_error_for_user(exc)) from exc

    def _run_tool_loop(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> str:
        compact_retry_used = False
        call_tracker = ToolCallTracker()
        last_compact_results: list[dict[str, Any]] = []

        for round_num in range(self.settings.max_tool_rounds):
            self._prepare_request_budget(messages, tools)

            try:
                response = chat_completion(
                    self.client,
                    model=self.settings.groq_model,
                    messages=messages,
                    tools=tools,
                    max_tokens=self.settings.max_output_tokens,
                )
            except APIStatusError as exc:
                if is_request_too_large(exc) and not compact_retry_used:
                    logger.warning("Request too large — compacting context and retrying once")
                    messages = aggressively_compact_messages(messages)
                    compact_retry_used = True
                    continue
                raise

            choice = response.choices[0]
            assistant_message = choice.message

            if not assistant_message.tool_calls:
                content = assistant_message.content or ""
                return content if content else "No response generated."

            messages.append(_assistant_message_to_dict(assistant_message))

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name or ""
                raw_args = tool_call.function.arguments
                args, parse_error = parse_tool_arguments(raw_args)

                if DEBUG_AGENT:
                    logger.info(
                        "Round %d tool=%s args=%s",
                        round_num + 1,
                        tool_name,
                        _safe_args(args),
                    )

                if parse_error:
                    result: dict[str, Any] = {
                        "error": parse_error,
                        "retryable": False,
                    }
                    compact = compact_tool_result(tool_name, result)
                else:
                    is_repeat, cached = call_tracker.check_repeat(tool_name, args)
                    if is_repeat and cached is not None:
                        logger.warning(
                            "Repeated tool call detected: %s %s",
                            tool_name,
                            _safe_args(args),
                        )
                        compact = cached
                    else:
                        result = self.tool_registry.execute(tool_name, args)
                        compact = compact_tool_result(tool_name, result)
                        call_tracker.store(tool_name, args, compact)
                        last_compact_results.append(compact)

                    if DEBUG_AGENT:
                        logger.info(
                            "Round %d result_summary=%s",
                            round_num + 1,
                            _summarize_result(compact),
                        )

                self.tool_trace.append({
                    "tool": tool_name,
                    "args": _safe_args(args),
                    "result_summary": _summarize_result(compact),
                    "estimated_result_tokens": estimate_messages_tokens([
                        {"role": "tool", "content": json.dumps(compact, default=str)},
                    ]),
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(compact, default=str),
                })

            # If all calls in this round were repeats, force final answer without more tools
            if round_num >= 1 and all(
                t.get("result_summary", {}).get("repeated_call") for t in self.tool_trace[-len(assistant_message.tool_calls):]
            ):
                try:
                    no_tool_response = chat_completion(
                        self.client,
                        model=self.settings.groq_model,
                        messages=messages + [{
                            "role": "user",
                            "content": (
                                "You already have the tool results. "
                                "Provide your final answer now without calling more tools."
                            ),
                        }],
                        tools=None,
                        max_tokens=self.settings.max_output_tokens,
                    )
                    content = no_tool_response.choices[0].message.content or ""
                    if content:
                        return content
                except APIStatusError:
                    pass

        if last_compact_results:
            return format_executive_fallback(last_compact_results)

        return format_executive_fallback([])

    def _prepare_request_budget(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> None:
        ok, total = validate_context_budget(
            messages,
            tools,
            max_tokens=self.settings.max_context_tokens,
        )
        self.last_request_tokens = total + estimate_tools_tokens(tools)

        log_request_diagnostics(
            model=self.settings.groq_model,
            messages=messages,
            tools=tools,
            max_output_tokens=self.settings.max_output_tokens,
        )

        if not ok:
            logger.warning(
                "Estimated request tokens (%d) exceed budget (%d) — trimming history",
                total,
                self.settings.max_context_tokens,
            )
            system = [m for m in messages if m.get("role") == "system"]
            rest = [m for m in messages if m.get("role") != "system"]
            messages.clear()
            messages.extend(system + rest[-4:])


class GroqAgentError(Exception):
    """Raised when the Groq API returns an error during agent execution."""


def _assistant_message_to_dict(message: Any) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "role": "assistant",
        "content": message.content,
    }
    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]
    return msg


def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for k, v in args.items():
        if k == "records" and isinstance(v, list):
            safe[k] = f"<{len(v)} records>"
        else:
            safe[k] = v
    return safe


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    if "error" in result:
        return {"error": result["error"]}
    summary: dict[str, Any] = {}
    for key in (
        "metric", "value", "currency", "definition", "operation",
        "row_count", "metrics", "match_summary", "board",
        "column_count", "returned_count", "customer_count",
        "do_not_sum", "repeated_call",
    ):
        if key in result:
            summary[key] = result[key]
    if "customers" in result:
        summary["customers_returned"] = len(result["customers"])
    if "sections" in result:
        summary["sections"] = list(result["sections"].keys())
    if "pipeline" in result:
        summary["pipeline"] = result["pipeline"]
    return summary
