"""
Shared state for the LangGraph agent.

Every node receives the full state and returns ONLY the keys it changes.
Two keys use reducers because the two retrieval nodes (Q3A and Q3B) run in
parallel and both write to them:

    timings  dicts are merged    {"graph_retrieve": 120} | {"vector_retrieve": 340}
    errors   lists are appended
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    # ---- input --------------------------------------------------------------
    question: str
    mode: str                         # "graphrag" or "vector" (baseline)

    # ---- Q2 router + entity linker -------------------------------------------
    route: dict[str, Any]             # {"template", "reason", "mentions"}
    entities: list[dict]              # linked entities (LinkedEntity.as_dict())
    run_graph: bool

    # ---- Q3A graph retrieval ---------------------------------------------------
    graph_facts: list[str]
    graph_queries: list[dict]
    graph_strategy: str

    # ---- Q3B hybrid vector retrieval -------------------------------------------
    passages: list[dict]
    vector_debug: dict

    # ---- Q4 context fusion -----------------------------------------------------
    context: str
    citations: dict[str, str]         # "G1" -> fact text, "V1" -> passage title/source
    evidence_found: bool

    # ---- Q5 / Q6 synthesis and grounding --------------------------------------
    draft: str
    grounding: dict[str, Any]

    # ---- Q7 output -------------------------------------------------------------
    answer: str
    status: str                       # "answered" or "refused"
    refusal_reason: str

    # ---- telemetry (reducers: safe for parallel writes) -----------------------
    timings: Annotated[dict[str, float], merge_dicts]
    errors: Annotated[list[str], operator.add]
