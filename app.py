"""Skylark Founder's Dashboard — Founder Intelligence Command Center."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from config.settings import get_settings
from src.agent.runner import AgentRunner
from src.dashboard.components import render_skylark_dashboard
from src.dashboard.data import load_monday_data
from src.dashboard.metrics import calculate_all_metrics
from src.data_service import create_data_service
from src.ui.chat import render_chat
from src.ui.theme import inject_skylark_theme
from src.utils.timer import timed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Skylark // Founder Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def get_data_service():
    return create_data_service(get_settings())


def create_agent() -> AgentRunner | None:
    try:
        return AgentRunner(data_service=get_data_service(), settings=get_settings())
    except Exception as exc:
        logger.debug("Agent unavailable: %s", type(exc).__name__)
        return None


@st.cache_data(ttl=180, show_spinner=False)
def load_dashboard_state(_version: int):
    settings = get_settings()
    ds = get_data_service()
    with timed("Dashboard total load"):
        data = load_monday_data(ds)
        metrics = calculate_all_metrics(ds, data, settings, top_n=10)
        return data, metrics, True


def main() -> None:
    settings = get_settings()
    debug_mode = settings.debug_mode
    inject_skylark_theme()

    cache_version = st.session_state.get("cache_version", 0)

    def _chat():
        render_chat(agent_factory=create_agent, debug_mode=debug_mode)

    data_ok = True
    load_ms = 0.0
    try:
        t0 = time.perf_counter()
        with st.spinner("Loading..."):
            data, metrics, data_ok = load_dashboard_state(cache_version)
        load_ms = (time.perf_counter() - t0) * 1000
    except Exception:
        st.warning("Some live data is temporarily unavailable. Please refresh.")
        if debug_mode:
            st.exception(Exception("Data load failed"))
        _chat()
        return

    if render_skylark_dashboard(
        data,
        metrics,
        data_ok=data_ok,
        debug_mode=debug_mode,
        load_ms=load_ms if debug_mode else None,
        data_service=get_data_service(),
        chat_renderer=_chat,
    ):
        get_data_service().invalidate_cache()
        st.cache_data.clear()
        st.session_state["cache_version"] = cache_version + 1
        st.rerun()


if __name__ == "__main__":
    main()
