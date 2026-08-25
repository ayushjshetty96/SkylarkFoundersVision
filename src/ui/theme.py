"""Skylark Founder Intelligence theme — aerospace command center."""

from __future__ import annotations

import streamlit as st


def inject_skylark_theme() -> None:
    st.markdown(
        """
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp {
        background: linear-gradient(180deg, #060a10 0%, #0a1018 50%, #080c12 100%);
        color: #d4dce6;
        font-family: 'IBM Plex Sans', system-ui, sans-serif;
    }

    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0.75rem;
        max-width: 1400px;
    }

    .fi-header { padding: 0.25rem 0 0.75rem 0; border-bottom: 1px solid #1a2836; margin-bottom: 0.5rem; }
    .fi-title {
        font-size: 1.15rem; font-weight: 700; letter-spacing: 0.14em;
        color: #e8f4fc; text-transform: uppercase;
    }
    .fi-sub { font-size: 0.72rem; color: #5a7088; margin-top: 0.15rem; }
    .fi-meta { font-size: 0.68rem; color: #4a90b8; margin-top: 0.35rem; font-family: 'IBM Plex Mono', monospace; }
    .fi-live { color: #3dd68c; font-weight: 600; }

    .fi-section {
        font-size: 0.62rem; font-weight: 600; letter-spacing: 0.16em;
        text-transform: uppercase; color: #4db8e8;
        margin: 0.75rem 0 0.4rem 0; padding-bottom: 0.2rem;
        border-bottom: 1px solid #152030;
    }

    .fi-kpi {
        background: rgba(12, 20, 30, 0.85);
        border: 1px solid #1e3044;
        border-radius: 4px;
        padding: 0.55rem 0.7rem;
        min-height: 72px;
        box-shadow: 0 0 12px rgba(45, 140, 200, 0.04);
    }
    .fi-kpi-label {
        font-size: 0.58rem; font-weight: 600; letter-spacing: 0.12em;
        color: #6a849c; text-transform: uppercase;
        font-family: 'IBM Plex Mono', monospace;
    }
    .fi-kpi-value { font-size: 1.25rem; font-weight: 700; color: #eef6fc; margin: 0.15rem 0; }
    .fi-kpi-hint { font-size: 0.65rem; color: #5a7088; }
    .fi-kpi-caveat { font-size: 0.62rem; color: #e8a838; margin-top: 0.2rem; }

    .fi-integrity-strip {
        background: rgba(8, 14, 22, 0.9);
        border: 1px solid #1a3044;
        border-radius: 4px;
        padding: 0.4rem 0.6rem;
        margin-bottom: 0.5rem;
    }
    .fi-section-inline {
        font-size: 0.62rem; font-weight: 600; letter-spacing: 0.14em;
        color: #4db8e8; text-transform: uppercase;
    }
    .fi-mono-sm { font-family: 'IBM Plex Mono', monospace; font-size: 0.6rem; color: #6a849c; }
    .fi-confidence {
        font-size: 0.62rem; font-weight: 700; letter-spacing: 0.1em;
        padding: 0.1rem 0.4rem; border-radius: 3px; margin-left: 0.5rem;
    }
    .fi-conf-high { background: rgba(61, 214, 140, 0.15); color: #3dd68c; border: 1px solid #2a9a68; }
    .fi-conf-medium { background: rgba(232, 168, 56, 0.12); color: #e8a838; border: 1px solid #a87828; }
    .fi-conf-low { background: rgba(232, 90, 90, 0.12); color: #e85a5a; border: 1px solid #a83838; }
    .fi-cat-label {
        font-size: 0.6rem; font-weight: 600; letter-spacing: 0.12em;
        color: #6a849c; text-transform: uppercase; margin: 0.5rem 0 0.25rem 0;
    }
    .fi-flow {
        font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
        color: #4db8e8; text-align: center; margin-bottom: 0.5rem; line-height: 1.6;
    }

    .fi-insight {
        background: rgba(10, 16, 24, 0.9);
        border: 1px solid #1a2836;
        border-radius: 4px;
        padding: 0.5rem 0.65rem;
        margin-bottom: 0.4rem;
        font-size: 0.78rem;
    }
    .fi-insight.fi-risk { border-left: 2px solid #e8a838; }
    .fi-insight.fi-opp { border-left: 2px solid #3dd68c; }
    .fi-insight-title { font-weight: 700; font-size: 0.68rem; letter-spacing: 0.06em; color: #a8c4dc; }
    .fi-insight-metric { font-size: 1rem; font-weight: 700; color: #eef6fc; margin: 0.15rem 0; }
    .fi-insight-body { color: #8aa0b4; line-height: 1.35; }
    .fi-insight-action { color: #4db8e8; font-size: 0.72rem; margin-top: 0.25rem; }

    .fi-mono { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: #5a849c; }

    div[data-testid="stMetric"] {
        background: rgba(12, 20, 30, 0.85);
        border: 1px solid #1e3044;
        border-radius: 4px;
        padding: 0.4rem 0.6rem;
    }
    div[data-testid="stMetric"] label { font-size: 0.65rem !important; color: #6a849c !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1rem !important; color: #eef6fc !important; }

    .stRadio > div { gap: 0.25rem !important; flex-wrap: wrap !important; }
    .stRadio label {
        font-size: 0.62rem !important; letter-spacing: 0.1em !important;
        font-weight: 600 !important; text-transform: uppercase !important;
    }

    .stDataFrame { font-size: 0.78rem; }
    #MainMenu, footer, header { visibility: hidden; }
    .stChatMessage { font-size: 0.88rem; }

    div[data-testid="stHorizontalBlock"] { gap: 0.5rem; }
</style>
        """,
        unsafe_allow_html=True,
    )


inject_jarvis_theme = inject_skylark_theme

from src.ui.formatting import fmt_inr, fmt_pct  # noqa: E402
