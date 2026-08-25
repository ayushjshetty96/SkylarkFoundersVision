"""Detect and prevent repeated identical tool calls."""

from __future__ import annotations

import json
from typing import Any


def normalize_tool_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize arguments for signature comparison."""
    normalized: dict[str, Any] = {}
    for key in sorted(args.keys()):
        value = args[key]
        if isinstance(value, dict):
            normalized[key] = {k: value[k] for k in sorted(value.keys())}
        elif isinstance(value, list):
            normalized[key] = sorted(value) if all(isinstance(v, str) for v in value) else value
        else:
            normalized[key] = value
    return normalized


def tool_call_signature(tool_name: str, args: dict[str, Any]) -> str:
    normalized = normalize_tool_arguments(args)
    return f"{tool_name}:{json.dumps(normalized, sort_keys=True, default=str)}"


class ToolCallTracker:
    """Track tool calls within a single agent run to prevent loops."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}
        self._counts: dict[str, int] = {}

    def check_repeat(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        sig = tool_call_signature(tool_name, args)
        count = self._counts.get(sig, 0)
        self._counts[sig] = count + 1
        if count > 0 and sig in self._results:
            return True, {
                **self._results[sig],
                "repeated_call": True,
                "note": (
                    "Identical tool call repeated — returning cached compact result. "
                    "Use this data to answer; do not call the same tool again."
                ),
            }
        return False, None

    def store(self, tool_name: str, args: dict[str, Any], compact_result: dict[str, Any]) -> None:
        sig = tool_call_signature(tool_name, args)
        self._results[sig] = compact_result

    def repeat_count(self, tool_name: str, args: dict[str, Any]) -> int:
        sig = tool_call_signature(tool_name, args)
        return self._counts.get(sig, 0)
