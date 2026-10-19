"""
Streamlit app (diagram box Q1).

    streamlit run app.py

Modes
    GraphRAG       full pipeline: router -> graph + vector -> fuse -> synthesize -> ground
    Vector-only    baseline: vector retrieval only (same LLM and prompts)
    Compare both   runs both and shows them side by side (useful for the demo video)
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from graphrag.agent.builder import ask, build_agent, total_latency_ms
from graphrag.config import get_settings

st.set_page_config(page_title="Fintara Org Knowledge", layout="wide")

MODES = {"GraphRAG": "graphrag", "Vector-only": "vector", "Compare both": "compare"}


# --------------------------------------------------------------------------- #
# Resources (created once per server process)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Connecting to Neo4j and Nebius ...")
def get_agent():
    return build_agent()


@st.cache_data
def sample_questions() -> list[str]:
    queries = json.loads(get_settings().eval_file.read_text())["queries"]
    return [q["question"] for q in queries]


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def render_answer(state: dict, title: str | None = None) -> None:
    """One answer with its evidence, grounding verdict and timings."""
    if title:
        st.markdown(f"#### {title}")

    status = state.get("status", "error")
    if status == "answered":
        st.success("Answered", icon=":material/check_circle:")
    else:
        st.error(f"Refused: {state.get('refusal_reason', '')}", icon=":material/block:")
    st.markdown(state.get("answer", ""))

    g = state.get("grounding", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latency", f"{state.get('wall_ms', 0) / 1000:.1f} s")
    c2.metric("Claims grounded", f"{g.get('supported', 0)}/{g.get('total', 0)}")
    c3.metric("Graph facts", len(state.get("graph_facts") or []))
    c4.metric("Passages", len(state.get("passages") or []))

    route = state.get("route", {})
    with st.expander("Route and entities (Q2)"):
        st.write(f"**Template:** `{route.get('template')}`  |  **Graph strategy:** `{state.get('graph_strategy', '-')}`")
        st.write(f"**Reason:** {route.get('reason', '')}")
        if state.get("entities"):
            st.dataframe(pd.DataFrame(state["entities"]), hide_index=True, width="stretch")

    with st.expander(f"Graph facts and Cypher (Q3A) - {len(state.get('graph_facts') or [])} facts"):
        for i, fact in enumerate(state.get("graph_facts") or [], start=1):
            st.markdown(f"**[G{i}]** {fact}")
        for q in state.get("graph_queries") or []:
            st.code(q["cypher"], language="cypher")
            st.caption(f"params={q['params']}  rows={q['row_count']}")

    with st.expander(f"Passages (Q3B) - {len(state.get('passages') or [])}"):
        for i, p in enumerate(state.get("passages") or [], start=1):
            st.markdown(f"**[V{i}] {p['title']}**  \n`{p['source']}: {p['path']}`  |  "
                        f"RRF {p['rrf_score']:.4f}  |  ranks {p['ranks']}")
            st.text(p["text"][:1200])
        debug = state.get("vector_debug") or {}
        if debug:
            st.caption(f"BM25 keywords: {debug.get('keywords')}")

    with st.expander("Grounding check (Q6)"):
        if g.get("claims"):
            st.dataframe(pd.DataFrame(g["claims"]), hide_index=True, width="stretch")
        else:
            st.write("Not run (refused earlier) or no claims returned.")

    with st.expander("Timings per node (ms)"):
        timings = state.get("timings", {})
        if timings:
            st.bar_chart(pd.Series(timings, name="ms"))
            st.caption(f"Sum by node (retrievers overlap): {total_latency_ms(state)} ms")

    if state.get("errors"):
        st.warning("Errors: " + "; ".join(state["errors"]))


def run_question(question: str, mode: str) -> dict:
    agent = get_agent()
    if mode == "compare":
        return {"compare": True, "graphrag": ask(agent, question, "graphrag"), "vector": ask(agent, question, "vector")}
    return {"compare": False, "single": ask(agent, question, mode)}


def render_result(result: dict) -> None:
    if result["compare"]:
        left, right = st.columns(2)
        with left:
            render_answer(result["graphrag"], "GraphRAG")
        with right:
            render_answer(result["vector"], "Vector-only")
    else:
        render_answer(result["single"])


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def main() -> None:
    settings = get_settings()
    st.title("Fintara Org Knowledge")
    st.caption("GraphRAG over Jira, Notion wiki and Slack · Neo4j graph + vector + full-text · LangGraph · Nebius")

    if "history" not in st.session_state:
        st.session_state.history = []          # list of (question, mode_label, result)

    with st.sidebar:
        st.header("Settings")
        mode_label = st.radio("Mode", list(MODES), index=0)
        st.divider()
        st.subheader("Sample questions")
        sample = st.selectbox("Pick one", ["(choose)"] + sample_questions(), label_visibility="collapsed")
        ask_sample = st.button("Ask sample question", width="stretch", disabled=sample == "(choose)")
        st.divider()
        st.caption(f"LLM: `{settings.llm_model}`")
        st.caption(f"Embeddings: `{settings.embedding_model}`")
        st.caption(f"Today: {settings.today}  |  grounding threshold: {settings.grounding_threshold}")
        if st.button("Clear chat", width="stretch"):
            st.session_state.history = []
            st.rerun()

    # Replay history
    for question, label, result in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(f"{question}  \n*mode: {label}*")
        with st.chat_message("assistant"):
            render_result(result)

    typed = st.chat_input("Ask about people, projects, services, decisions, incidents ...")
    question = typed or (sample if ask_sample else None)
    if question:
        with st.chat_message("user"):
            st.markdown(f"{question}  \n*mode: {mode_label}*")
        with st.chat_message("assistant"):
            with st.spinner("Routing, retrieving, answering, checking grounding ..."):
                result = run_question(question, MODES[mode_label])
            render_result(result)
        st.session_state.history.append((question, mode_label, result))


if __name__ == "__main__":
    main()
