"""
Wire the nodes into a LangGraph StateGraph.

                          START
                            |
                         router (Q2)
                    /                 \\
        graph_retrieve (Q3A)    vector_retrieve (Q3B)      <- parallel when entities found
                    \\                 /
                          fuse (Q4) ---- no evidence ----> refuse (Q7b)
                            |
                       synthesize (Q5) - INSUFFICIENT ----> refuse
                            |
                         ground (Q6) ---- fail -----------> refuse
                            |
                        finalize (Q7a)
                            |
                           END

Usage:
    agent = build_agent()                     # real clients from .env
    state = ask(agent, "Who owns ledger-db?", mode="graphrag")
    print(state["answer"])
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graphrag.agent.nodes import AgentDeps, AgentNodes
from graphrag.agent.state import AgentState
from graphrag.config import Settings, get_settings


def build_deps(settings: Settings | None = None) -> AgentDeps:
    """Create real clients (Nebius + Neo4j) and the retrievers."""
    from graphrag.clients import get_embeddings, get_graph, get_llm
    from graphrag.retrieval.entity_linker import EntityLinker
    from graphrag.retrieval.graph_retriever import GraphRetriever
    from graphrag.retrieval.hybrid_retriever import HybridRetriever
    from graphrag.retrieval.text2cypher import Text2Cypher

    s = settings or get_settings()
    graph = get_graph(s)
    llm = get_llm(s)
    judge = get_llm(s, model=s.judge_model)
    return AgentDeps(
        llm=llm,
        judge_llm=judge,
        linker=EntityLinker(graph, s.today),
        graph_retriever=GraphRetriever(graph, Text2Cypher(graph, llm) if s.enable_text2cypher else None),
        hybrid_retriever=HybridRetriever(graph, get_embeddings(s), s, rerank_llm=llm),
        today=s.today,
        max_context_tokens=s.max_context_tokens,
        grounding_threshold=s.grounding_threshold,
    )


def build_graph(deps: AgentDeps):
    """Compile the StateGraph from injected dependencies."""
    n = AgentNodes(deps)
    g = StateGraph(AgentState)

    g.add_node("router", n.router)
    g.add_node("graph_retrieve", n.graph_retrieve)
    g.add_node("vector_retrieve", n.vector_retrieve)
    g.add_node("fuse", n.fuse)
    g.add_node("synthesize", n.synthesize)
    g.add_node("ground", n.ground)
    g.add_node("finalize", n.finalize)
    g.add_node("refuse", n.refuse)

    g.add_edge(START, "router")
    # Returning a LIST of node names runs them in parallel (same super-step)
    g.add_conditional_edges("router", n.route_after_router, ["graph_retrieve", "vector_retrieve"])
    # Separate edges: fuse runs once after whichever retrievers ran have finished
    g.add_edge("graph_retrieve", "fuse")
    g.add_edge("vector_retrieve", "fuse")
    g.add_conditional_edges("fuse", n.route_after_fuse, ["synthesize", "refuse"])
    g.add_conditional_edges("synthesize", n.route_after_synthesis, ["ground", "refuse"])
    g.add_conditional_edges("ground", n.route_after_grounding, ["finalize", "refuse"])
    g.add_edge("finalize", END)
    g.add_edge("refuse", END)
    return g.compile()


def build_agent(settings: Settings | None = None):
    return build_graph(build_deps(settings))


def ask(agent, question: str, mode: str = "graphrag") -> AgentState:
    """Run one question. mode = "graphrag" (full pipeline) or "vector" (baseline)."""
    import time

    if mode not in {"graphrag", "vector"}:
        raise ValueError("mode must be 'graphrag' or 'vector'")
    start = time.perf_counter()
    state = agent.invoke({"question": question, "mode": mode, "timings": {}, "errors": []})
    state["wall_ms"] = round((time.perf_counter() - start) * 1000, 1)   # end-to-end latency
    return state


def total_latency_ms(state: AgentState) -> float:
    """Sum of node timings. The two retrievers overlap, so count only the slower one."""
    t = dict(state.get("timings", {}))
    parallel = max(t.pop("graph_retrieve", 0.0), t.pop("vector_retrieve", 0.0))
    return round(sum(t.values()) + parallel, 1)
