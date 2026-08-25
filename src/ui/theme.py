"""Skylark Founder's Dashboard theme."""

from __future__ import annotations

import streamlit as st


def inject_skylark_theme() -> None:
    st.markdown(
        """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    .stApp {
        background: #0f1419;
        color: #e8eaed;
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 0.75rem;
        padding-bottom: 1rem;
        max-width: 1320px;
    }

    .sk-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: 0.5rem 0 1.25rem 0;
        border-bottom: 1px solid #1e2a38;
        margin-bottom: 1rem;
    }

    .sk-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #f0f4f8;
        letter-spacing: 0.02em;
        margin: 0;
    }

    .sk-subtitle {
        font-size: 0.8rem;
        color: #7a8a9a;
        margin-top: 0.2rem;
    }

    .sk-meta {
        text-align: right;
        font-size: 0.75rem;
        color: #7a8a9a;
    }

    .sk-live {
        color: #3fb950;
        font-weight: 600;
    }

    .sk-section {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #5b9fd4;
        margin: 1.25rem 0 0.6rem 0;
    }

    .sk-kpi-card {
        background: #161d27;
        border: 1px solid #243040;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        min-height: 88px;
    }

    .sk-kpi-label {
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        color: #7a8a9a;
        text-transform: uppercase;
    }

    .sk-kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #f0f4f8;
        margin: 0.25rem 0;
        line-height: 1.2;
    }

    .sk-kpi-desc {
        font-size: 0.72rem;
        color: #9aa8b5;
    }

    .sk-health-score {
        font-size: 2rem;
        font-weight: 700;
        color: #5b9fd4;
    }

    .sk-insight {
        background: #161d27;
        border-left: 3px solid #5b9fd4;
        padding: 0.6rem 0.9rem;
        font-size: 0.82rem;
        color: #b8c4ce;
        margin-top: 0.5rem;
        border-radius: 0 4px 4px 0;
    }

    div[data-testid="stMetric"] {
        background: #161d27;
        border: 1px solid #243040;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
    }

    div[data-testid="stMetric"] label { font-size: 0.7rem !important; color: #7a8a9a !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
        color: #f0f4f8 !important;
    }

    .stDataFrame { font-size: 0.82rem; }

    #MainMenu, footer, header { visibility: hidden; }

    .stChatMessage { font-size: 0.9rem; }
</style>
        """,
        unsafe_allow_html=True,
    )


# Backward compatibility
inject_jarvis_theme = inject_skylark_theme

from src.ui.formatting import fmt_inr, fmt_pct  # noqa: E402
