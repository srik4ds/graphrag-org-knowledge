"""
QUERY TIME orchestration with LangGraph (diagram boxes Q2 to Q7).

    state.py     the shared AgentState passed between nodes
    prompts.py   every prompt in one place
    nodes.py     one method per box: router, graph_retrieve, vector_retrieve,
                 fuse, synthesize, ground, refuse, finalize
    builder.py   wires the nodes into a LangGraph StateGraph and exposes ask()
"""
