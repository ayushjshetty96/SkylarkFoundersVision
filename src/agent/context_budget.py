"""Token estimation, history trimming, and tool-result compaction."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Rough chars-per-token for English/JSON (conservative)
CHARS_PER_TOKEN = 4
DEFAULT_MAX_CONTEXT_TOKENS = 6000
DEFAULT_MAX_TOOL_RESULT_CHARS = 2000
MAX_HISTORY_MESSAGES = 6


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif content is not None:
            total += estimate_tokens(json.dumps(content, default=str))
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            total += estimate_tokens(json.dumps(tool_calls, default=str))
    return total


def estimate_tools_tokens(tools: list[dict[str, Any]]) -> int:
    return estimate_tokens(json.dumps(tools, default=str))


def trim_history(
    history: list[dict[str, str]],
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> list[dict[str, str]]:
    """Keep the most recent user/assistant turns."""
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


def compact_tool_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Shrink tool output before sending to the LLM."""
    if "error" in result:
        return {"error": result["error"], "retryable": result.get("retryable", False)}

    if tool_name == "query_items":
        return _compact_query(result)
    if tool_name == "join_by_company":
        return _compact_join(result)
    if tool_name == "get_board_schema":
        return _compact_schema(result)
    if tool_name == "generate_leadership_snapshot":
        return _compact_leadership(result)
    if tool_name == "aggregate":
        return _compact_aggregate(result)
    if tool_name == "business_metric":
        return result  # already compact
    if tool_name == "customer_analysis":
        return _compact_customer_analysis(result)
    if tool_name in (
        "customer_ranking", "customer_health", "pipeline_summary",
        "pipeline_analysis", "operations_summary", "sector_summary",
    ):
        return result

    return _truncate_dict(result)


def _compact_customer_analysis(result: dict[str, Any]) -> dict[str, Any]:
    compact = dict(result)
    if "customers" in compact and len(compact["customers"]) > 15:
        compact["customers"] = compact["customers"][:15]
        compact["customers_truncated"] = True
    if "summary" in compact and isinstance(compact["summary"], dict):
        for key, val in compact["summary"].items():
            if isinstance(val, list) and len(val) > 10:
                compact["summary"][key] = val[:10]
    return compact


def _compact_query(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "board": result.get("board"),
        "row_count": result.get("row_count"),
        "filters_applied": result.get("filters_applied", {}),
    }
    records = result.get("records")
    if records:
        default_limit = 5
        limit = min(len(records), result.get("returned_count", default_limit))
        compact["returned_count"] = limit
        compact["records"] = records[:limit]
        if len(records) > limit:
            compact["truncated"] = True
            compact["note"] = f"Showing {limit} of {len(records)} rows. Use aggregate or business_metric for totals."
    else:
        compact["note"] = result.get(
            "note",
            "Row count only. Use business_metric or aggregate for KPIs.",
        )
    return compact


def _compact_aggregate(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "metrics": result.get("metrics", {}),
        "group_by": result.get("group_by", []),
        "valid_row_count": result.get("valid_row_count"),
        "total_row_count": result.get("total_row_count"),
        "excluded_from_metrics": result.get("excluded_from_metrics", {}),
        "warnings": (result.get("warnings") or [])[:5],
    }
    groups = result.get("groups") or []
    if groups:
        compact["groups"] = groups[:20]
        if len(groups) > 20:
            compact["groups_truncated"] = True
            compact["total_groups"] = len(groups)
    return compact


def _compact_join(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "match_summary": result.get("match_summary"),
        "unmatched": {
            "wo_only_count": len(result.get("unmatched", {}).get("wo_only", []) or []),
            "deal_only_count": result.get("unmatched", {}).get("deal_only_count", 0),
        },
        "warnings": (result.get("warnings") or [])[:3],
    }
    # Compact company list: stats only, no embedded deal/wo arrays
    companies = []
    for c in (result.get("companies") or [])[:15]:
        companies.append({
            "company_code": c.get("company_code"),
            "match_confidence": c.get("match_confidence"),
            "deal_count": len(c.get("deals") or []),
            "work_order_count": len(c.get("work_orders") or []),
            "total_open_pipeline_value": c.get("total_open_pipeline_value"),
            "total_ar": c.get("total_ar"),
        })
    compact["companies_sample"] = companies
    if len(result.get("companies") or []) > 15:
        compact["companies_truncated"] = True
    return compact


def _compact_schema(result: dict[str, Any]) -> dict[str, Any]:
    columns = result.get("columns") or []
    if isinstance(columns, dict):
        fields = list(columns.keys())
    elif isinstance(columns, list) and columns and isinstance(columns[0], dict):
        fields = [c.get("title") or c.get("id") for c in columns]
    else:
        fields = []
    return {
        "board": result.get("board"),
        "board_name": result.get("board_name"),
        "item_count_estimate": result.get("item_count_estimate"),
        "column_count": result.get("column_count", len(fields)),
        "fields": fields[:50],
    }


def _compact_leadership(result: dict[str, Any]) -> dict[str, Any]:
    sections = result.get("sections") or {}
    pipeline = sections.get("pipeline_headline") or {}
    cash = sections.get("cash_collection") or {}
    ops = sections.get("operations") or {}
    risks = sections.get("cross_board_risks") or {}
    dq = sections.get("data_quality") or {}
    pipeline_by_stage = sections.get("pipeline_by_stage") or {}
    stage_groups = pipeline_by_stage.get("groups") if isinstance(pipeline_by_stage, dict) else []
    if stage_groups is None:
        stage_groups = []

    return {
        "as_of": result.get("as_of"),
        "source": result.get("source"),
        "pipeline": {
            "open_deal_count": pipeline.get("open_deal_count"),
            "raw_pipeline_inr": pipeline.get("raw_pipeline_value_inr"),
            "weighted_pipeline_inr": pipeline.get("weighted_pipeline_value_inr"),
            "missing_deal_value_count": pipeline.get("missing_deal_value_count"),
        },
        "cash": {
            "total_ar_inr": cash.get("total_ar_inr"),
            "priority_ar_inr": cash.get("priority_ar_inr"),
            "top_ar_companies": (cash.get("top_ar_companies") or [])[:5],
        },
        "operations": {
            "not_started": ops.get("not_started"),
            "ongoing": ops.get("ongoing"),
        },
        "pipeline_by_stage": stage_groups[:10],
        "cross_board_risks": {
            "stale_open_deals": risks.get("stale_open_deals_count"),
            "companies_pipeline_and_ar": (risks.get("companies_with_pipeline_and_ar") or [])[:5],
        },
        "data_quality": {
            "work_order_count": dq.get("work_order_count"),
            "deal_count": dq.get("deal_count"),
            "missing_deal_values": dq.get("missing_deal_values"),
        },
    }


def _truncate_dict(result: dict[str, Any], max_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS) -> dict[str, Any]:
    serialized = json.dumps(result, default=str)
    if len(serialized) <= max_chars:
        return result
    return {
        "truncated": True,
        "preview": serialized[:max_chars],
        "note": "Result truncated for token budget. Request a more specific metric.",
    }


def validate_context_budget(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
) -> tuple[bool, int]:
    total = estimate_messages_tokens(messages)
    if tools:
        total += estimate_tools_tokens(tools)
    return total <= max_tokens, total


def aggressively_compact_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Emergency compaction for 413: keep system + last user + last tool round only."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    users = [m for m in non_system if m.get("role") == "user"]
    last_user = users[-1:] if users else []
    tail = non_system[-4:] if len(non_system) > 4 else non_system
    compacted: list[dict[str, Any]] = []
    for msg in system + last_user + tail:
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if len(content) > DEFAULT_MAX_TOOL_RESULT_CHARS:
                compacted.append({
                    **msg,
                    "content": content[:DEFAULT_MAX_TOOL_RESULT_CHARS] + "...[truncated]",
                })
                continue
        compacted.append(msg)
    return compacted


def log_request_diagnostics(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_output_tokens: int | None = None,
) -> None:
    if os.getenv("DEBUG_TOKEN_USAGE", "").lower() not in ("1", "true", "yes"):
        return
    msg_tokens = estimate_messages_tokens(messages)
    tool_tokens = estimate_tools_tokens(tools) if tools else 0
    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    logger.info(
        "Groq request:\n"
        "  model: %s\n"
        "  messages: %d\n"
        "  tools: %d\n"
        "  estimated input tokens: %d\n"
        "  max output tokens: %s\n"
        "  system prompt chars: %d",
        model,
        len(messages),
        len(tools or []),
        msg_tokens + tool_tokens,
        max_output_tokens,
        len(system) if isinstance(system, str) else 0,
    )
