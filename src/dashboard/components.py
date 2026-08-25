"""Skylark dashboard UI — delegates to Founder Intelligence command center."""

from __future__ import annotations

from src.dashboard.command_center import render_command_center
from src.dashboard.components_legacy import render_data_diagnostics  # noqa: F401

# Re-export legacy render helpers for tests / backward compatibility
from src.dashboard.components_legacy import (  # noqa: F401
    render_business_health,
    render_customer_intelligence,
    render_executive_overview,
    render_operational_health,
    render_pipeline,
    render_revenue_cash,
)


def render_skylark_dashboard(
    data,
    metrics,
    *,
    data_ok: bool,
    debug_mode: bool = False,
    load_ms: float | None = None,
    data_service=None,
    chat_renderer=None,
) -> bool:
    return render_command_center(
        data,
        metrics,
        data_service,
        data_ok=data_ok,
        debug_mode=debug_mode,
        load_ms=load_ms,
        chat_renderer=chat_renderer,
    )


render_full_dashboard = render_skylark_dashboard
