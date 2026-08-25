"""OpenAI-compatible function-calling tool registry and dispatch."""

from __future__ import annotations

import json
from typing import Any, Callable

from config.settings import Settings
from src.data_service import DataService
from src.tools.business_metric import SUPPORTED_METRICS, business_metric_tool
from src.tools.customer_analysis import SUPPORTED_OPERATIONS, SORT_FIELDS, customer_analysis_tool
from src.tools.join_tool import join_by_company_tool
from src.tools.leadership import generate_leadership_snapshot
from src.tools.query import query_items
from src.tools.schema import get_board_schema
from src.tools.server_aggregate import server_aggregate_tool
from src.tools.summary_tools import (
    customer_health_tool,
    customer_ranking_tool,
    operations_summary_tool,
    pipeline_summary_tool,
    sector_summary_tool,
)
from src.tools.pipeline_analysis import pipeline_analysis_tool

PERIOD_ENUM = [
    "today", "this_week", "this_month", "this_quarter", "this_year",
]

# Compact tool definitions — no embedded business schema
OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "customer_analysis",
            "description": (
                "Analyze customers/companies using company-code join. "
                "Use for customer rankings, good customers, overview, receivables, pipeline. "
                "ONE call per customer question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": SUPPORTED_OPERATIONS,
                        "description": (
                            "good_customers | customer_overview | top_customers | "
                            "customer_receivables | customer_pipeline | pipeline_and_receivables"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max customers to return (default 10)",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": SORT_FIELDS,
                        "description": "Sort field for top_customers (default collected)",
                    },
                },
                "required": ["operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "customer_ranking",
            "description": "Top/best/risky customers. ONE call. ranking: best|risk|receivables|pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "ranking": {
                        "type": "string",
                        "enum": [
                            "best", "risk", "receivables", "pipeline", "top",
                            "overview", "compare", "major",
                        ],
                        "description": (
                            "best=good customers, risk=attention, receivables=who owes most, "
                            "overview=talk about customers, compare=major customer cross-board"
                        ),
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": SORT_FIELDS,
                        "description": "Optional sort when ranking not set",
                    },
                    "limit": {"type": "integer", "description": "Max 15"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "customer_health",
            "description": "Customer health classification (HEALTHY/WATCH/AT RISK). ONE call.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_summary",
            "description": (
                "Open pipeline summary. Optional sector/period filters. "
                "Use pipeline_analysis for sector+quarter questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Optional sector e.g. Energy"},
                    "period": {
                        "type": "string",
                        "enum": PERIOD_ENUM,
                        "description": "Optional period e.g. this_quarter",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_analysis",
            "description": (
                "Filtered pipeline analysis by sector and/or period. ONE call for "
                "'energy sector this quarter' style questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Sector filter e.g. Energy"},
                    "period": {
                        "type": "string",
                        "enum": PERIOD_ENUM,
                        "description": "Relative period e.g. this_quarter",
                    },
                    "period_start": {"type": "string", "description": "Optional ISO start date"},
                    "period_end": {"type": "string", "description": "Optional ISO end date"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "operations_summary",
            "description": "Work order execution and billing status summary. ONE call.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sector_summary",
            "description": (
                "Sector performance: pipeline, contract value, work orders. "
                "Optional sector and period filters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "sector": {"type": "string", "description": "Filter to one sector e.g. Energy"},
                    "period": {
                        "type": "string",
                        "enum": PERIOD_ENUM,
                        "description": "Optional period for pipeline subset",
                    },
                    "focus": {
                        "type": "string",
                        "enum": ["pipeline", "revenue", "work_orders", "collections"],
                        "description": "Optional performance dimension",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "business_metric",
            "description": (
                "Get a deterministic business KPI from live Monday.com data. "
                "Use for revenue (total_revenue), pipeline (open_pipeline), "
                "receivables, and counts. Call this first for KPI questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": SUPPORTED_METRICS + ["total_revenue", "revenue"],
                        "description": (
                            "KPI name. Use total_revenue for revenue questions "
                            "(returns separate contract/billed/collected/receivables — do not sum)."
                        ),
                    },
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate",
            "description": (
                "Calculate deterministic metrics (sum, count, average, grouped totals) "
                "on work_orders or deals. Data is fetched server-side."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "board": {
                        "type": "string",
                        "description": "work_orders or deals",
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional grouping fields",
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": 'e.g. [{"name": "total", "field": "deal_value", "op": "sum"}]',
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional field filters before aggregation",
                    },
                },
                "required": ["board", "metrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_items",
            "description": (
                "Query normalized Monday records. Use only when specific records are needed. "
                "Returns row count by default, not full datasets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "board": {"type": "string", "description": "work_orders or deals"},
                    "filters": {"type": "object", "description": "Optional field filters"},
                    "include_records": {
                        "type": "boolean",
                        "description": "Set true to return sample rows (default false)",
                    },
                    "limit": {"type": "integer", "description": "Max rows when include_records=true"},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to include in sample rows",
                    },
                },
                "required": ["board"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "join_by_company",
            "description": "Join work orders and deals using normalized company codes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional filter to specific company codes",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_leadership_snapshot",
            "description": (
                "Return a compact executive snapshot: pipeline, receivables, operations, data quality."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_board_schema",
            "description": "Return available logical fields when schema information is genuinely needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board": {"type": "string", "description": "work_orders or deals"},
                },
                "required": ["board"],
            },
        },
    },
]


def parse_tool_arguments(raw: str | dict | None) -> tuple[dict[str, Any], str | None]:
    """Parse tool arguments from JSON string or dict. Returns (args, error)."""
    if raw is None:
        return {}, None
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}, None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return {}, f"Malformed tool arguments JSON: {exc}"
        if not isinstance(parsed, dict):
            return {}, "Tool arguments must be a JSON object"
        return parsed, None
    return {}, f"Unsupported tool arguments type: {type(raw).__name__}"


class ToolRegistry:
    def __init__(self, data_service: DataService, settings: Settings):
        self.data_service = data_service
        self.settings = settings
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "customer_ranking": self._customer_ranking,
            "customer_health": self._customer_health,
            "pipeline_summary": self._pipeline_summary,
            "pipeline_analysis": self._pipeline_analysis,
            "operations_summary": self._operations_summary,
            "sector_summary": self._sector_summary,
            "customer_analysis": self._customer_analysis,
            "business_metric": self._business_metric,
            "get_board_schema": self._get_board_schema,
            "query_items": self._query_items,
            "join_by_company": self._join_by_company,
            "aggregate": self._aggregate,
            "generate_leadership_snapshot": self._leadership_snapshot,
        }

    def get_tools(self) -> list[dict[str, Any]]:
        return OPENAI_TOOLS

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}", "retryable": False}
        try:
            return handler(args)
        except Exception as exc:
            return {"error": str(exc), "retryable": False}

    def _customer_ranking(self, args: dict[str, Any]) -> dict[str, Any]:
        return customer_ranking_tool(
            self.data_service,
            limit=int(args.get("limit", 10)),
            sort_by=args.get("sort_by", "collected"),
            ranking=args.get("ranking"),
            settings=self.settings,
        )

    def _customer_health(self, args: dict[str, Any]) -> dict[str, Any]:
        return customer_health_tool(
            self.data_service,
            limit=int(args.get("limit", 10)),
            settings=self.settings,
        )

    def _pipeline_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        return pipeline_summary_tool(
            self.data_service,
            settings=self.settings,
            sector=args.get("sector"),
            period=args.get("period"),
        )

    def _pipeline_analysis(self, args: dict[str, Any]) -> dict[str, Any]:
        return pipeline_analysis_tool(
            self.data_service,
            sector=args.get("sector"),
            period=args.get("period"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
            settings=self.settings,
        )

    def _operations_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        return operations_summary_tool(self.data_service, settings=self.settings)

    def _sector_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        return sector_summary_tool(
            self.data_service,
            limit=int(args.get("limit", 10)),
            sector=args.get("sector"),
            period=args.get("period"),
            focus=args.get("focus"),
            settings=self.settings,
        )

    def _customer_analysis(self, args: dict[str, Any]) -> dict[str, Any]:
        return customer_analysis_tool(
            self.data_service,
            args["operation"],
            limit=int(args.get("limit", 10)),
            sort_by=args.get("sort_by", "collected"),
            settings=self.settings,
        )

    def _business_metric(self, args: dict[str, Any]) -> dict[str, Any]:
        return business_metric_tool(
            self.data_service,
            args["metric"],
            settings=self.settings,
        )

    def _get_board_schema(self, args: dict[str, Any]) -> dict[str, Any]:
        return get_board_schema(self.data_service, args["board"])

    def _query_items(self, args: dict[str, Any]) -> dict[str, Any]:
        return query_items(
            self.data_service,
            args["board"],
            filters=args.get("filters"),
            include_records=bool(args.get("include_records", False)),
            limit=int(args.get("limit", 5)),
            fields=args.get("fields"),
        )

    def _join_by_company(self, args: dict[str, Any]) -> dict[str, Any]:
        return join_by_company_tool(
            self.data_service,
            company_codes=args.get("company_codes"),
        )

    def _aggregate(self, args: dict[str, Any]) -> dict[str, Any]:
        return server_aggregate_tool(
            self.data_service,
            board=args["board"],
            group_by=args.get("group_by"),
            metrics=args.get("metrics"),
            filters=args.get("filters"),
        )

    def _leadership_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        return generate_leadership_snapshot(self.data_service, self.settings)
