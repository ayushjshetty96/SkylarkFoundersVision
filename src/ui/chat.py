"""Ask Skylark — executive AI assistant."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from src.agent.runner import AgentRunner, GroqAgentError
from src.ui.components import render_tool_trace

SUGGESTED_QUERIES = [
    "What should I focus on this week?",
    "Who owes us the most?",
    "Show pipeline risks",
    "Which sector is strongest?",
    "How is Energy performing?",
    "Which customers need attention?",
    "Compare pipeline and operations",
]


def render_chat(
    agent: AgentRunner | None = None,
    *,
    debug_mode: bool = False,
    agent_factory=None,
) -> None:
    st.markdown('<div class="fi-section">ASK SKYLARK</div>', unsafe_allow_html=True)
    st.caption("Answer · Evidence · Insight · Action")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None

    cols = st.columns(len(SUGGESTED_QUERIES))
    for col, query in zip(cols, SUGGESTED_QUERIES):
        with col:
            if st.button(query, key=f"sk_{query[:18]}", use_container_width=True):
                st.session_state.pending_prompt = query
                st.rerun()

    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(msg["content"])
            if debug_mode and msg.get("tool_trace"):
                render_tool_trace(msg["tool_trace"])

    prompt = st.session_state.pending_prompt
    if prompt:
        st.session_state.pending_prompt = None
    else:
        prompt = st.chat_input("Ask Skylark about your business...")

    if not prompt:
        return

    if agent is None and agent_factory is not None:
        agent = agent_factory()

    if agent is None:
        st.info("Skylark AI is temporarily unavailable.")
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]
            try:
                response = agent.run(prompt, history=history)
            except GroqAgentError:
                st.warning("Skylark AI is temporarily unavailable. Please try again shortly.")
                return
            except Exception:
                st.warning("Skylark AI is temporarily unavailable. Please try again shortly.")
                return
            # Strip internal footers if model adds them
            for footer in ("\n\n*Data used", "\n\nData used", "*Data used:*"):
                if footer.lower() in response.lower():
                    response = response.split(footer)[0].split("Data used")[0].strip()
            st.markdown(response)
            if debug_mode:
                render_tool_trace(agent.tool_trace)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "tool_trace": list(agent.tool_trace) if debug_mode else [],
    })
