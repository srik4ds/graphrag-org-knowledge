"""
LangGraph nodes: one method per diagram box.

    Q2   router            LLM extracts mentions + template, linker resolves node ids
    Q3A  graph_retrieve    Cypher template / Text2Cypher -> graph facts      (parallel)
    Q3B  vector_retrieve   dense + BM25 + RRF -> parent passages             (parallel)
    Q4   fuse              merge, tag [G#]/[V#], trim to token budget
    Q5   synthesize        LLM drafts a cited answer from the context only
    Q6   ground            LLM judge checks every claim against its citation
    Q7a  finalize          return the answer
    Q7b  refuse            return the fixed refusal message

Plus the routing functions that decide which node runs next.

Dependencies (LLM, retrievers, linker) are injected through AgentDeps, so tests can
pass fakes and the app can pass real clients.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Callable

from langchain_core.language_models import BaseChatModel

from graphrag.agent import prompts
from graphrag.agent.state import AgentState
from graphrag.retrieval.cypher_templates import TEMPLATES, describe_templates
from graphrag.retrieval.entity_linker import EntityLinker, LinkedEntity
from graphrag.retrieval.graph_retriever import GraphRetriever
from graphrag.retrieval.hybrid_retriever import HybridRetriever
from graphrag.schema import SCHEMA_DESCRIPTION
from graphrag.utils import log, parse_json_object, timer, token_len, trim_to_tokens


@dataclass
class AgentDeps:
    """Everything the nodes need. Built once by builder.build_deps()."""
    llm: BaseChatModel
    judge_llm: BaseChatModel
    linker: EntityLinker
    graph_retriever: GraphRetriever
    hybrid_retriever: HybridRetriever
    today: str
    max_context_tokens: int = 6000
    grounding_threshold: float = 0.8


def timed(node_name: str) -> Callable:
    """Decorator: record how long a node took in state['timings'] (milliseconds)."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(self, state: AgentState) -> dict:
            with timer() as t:
                update = fn(self, state)
            update = dict(update or {})
            update["timings"] = {node_name: t["ms"]}
            return update
        return wrapper
    return decorator


class AgentNodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.d = deps

    # ================================================================== #
    # Q2  Router + entity linker
    # ================================================================== #
    @timed("router")
    def router(self, state: AgentState) -> dict:
        # Baseline mode: plain vector RAG, no router LLM call, no graph
        if state.get("mode") == "vector":
            return {"route": {"template": None, "reason": "vector-only baseline", "mentions": []},
                    "entities": [], "run_graph": False}

        prompt = prompts.ROUTER_PROMPT.format(today=self.d.today, schema=SCHEMA_DESCRIPTION,
                                              templates=describe_templates(), question=state["question"])
        try:
            parsed = parse_json_object(self.d.llm.invoke(prompt).content)
        except Exception as exc:  # noqa: BLE001  (bad JSON -> degrade to vector-only)
            log.warning("Router failed (%s); continuing with vector retrieval only", exc)
            return {"route": {"template": None, "reason": f"router error: {exc}", "mentions": []},
                    "entities": [], "run_graph": False, "errors": [f"router: {exc}"]}

        mentions = [m for m in parsed.get("mentions", []) if isinstance(m, dict)]
        template = parsed.get("template")
        template = template if template in TEMPLATES else None

        linked: list[LinkedEntity] = self.d.linker.link(mentions) if mentions else []
        return {
            "route": {"template": template, "reason": parsed.get("reason", ""), "mentions": mentions},
            "entities": [e.as_dict() for e in linked],
            # The rule from the design: entities found -> graph + vector; none -> vector only
            "run_graph": bool(linked),
        }

    @staticmethod
    def route_after_router(state: AgentState) -> list[str]:
        """Fan out: both retrievers in parallel, or vector only."""
        return ["graph_retrieve", "vector_retrieve"] if state.get("run_graph") else ["vector_retrieve"]

    # ================================================================== #
    # Q3A  Graph retrieval
    # ================================================================== #
    @timed("graph_retrieve")
    def graph_retrieve(self, state: AgentState) -> dict:
        entities = [LinkedEntity(**e) for e in state.get("entities", [])]
        try:
            result = self.d.graph_retriever.retrieve(state["question"], state["route"].get("template"), entities)
        except Exception as exc:  # noqa: BLE001
            log.warning("Graph retrieval failed: %s", exc)
            return {"graph_facts": [], "graph_queries": [], "graph_strategy": "error",
                    "errors": [f"graph_retrieve: {exc}"]}
        return {"graph_facts": result.facts, "graph_queries": result.queries, "graph_strategy": result.strategy}

    # ================================================================== #
    # Q3B  Hybrid vector retrieval
    # ================================================================== #
    @timed("vector_retrieve")
    def vector_retrieve(self, state: AgentState) -> dict:
        try:
            result = self.d.hybrid_retriever.retrieve(state["question"])
        except Exception as exc:  # noqa: BLE001
            log.warning("Vector retrieval failed: %s", exc)
            return {"passages": [], "vector_debug": {}, "errors": [f"vector_retrieve: {exc}"]}
        return {"passages": [p.__dict__ for p in result.passages], "vector_debug": result.debug}

    # ================================================================== #
    # Q4  Context fusion
    # ================================================================== #
    @timed("fuse")
    def fuse(self, state: AgentState) -> dict:
        facts = state.get("graph_facts") or []
        passages = state.get("passages") or []
        citations: dict[str, str] = {}
        budget = self.d.max_context_tokens

        # Graph facts first: they are short and precise
        lines = ["GRAPH FACTS:"] if facts else []
        for i, fact in enumerate(dict.fromkeys(facts), start=1):        # dict.fromkeys = ordered dedupe
            tag = f"G{i}"
            lines.append(f"[{tag}] {fact}")
            citations[tag] = fact
        used = token_len("\n".join(lines))

        # Then passages, each trimmed so the total stays within budget
        if passages:
            lines.append("\nPASSAGES:")
        seen_docs = set()
        for i, p in enumerate(passages, start=1):
            if p["parent_id"] in seen_docs:
                continue
            seen_docs.add(p["parent_id"])
            remaining = budget - used
            if remaining < 80:
                break
            tag = f"V{i}"
            header = f"[{tag}] (source: {p['source']} | {p['title']})"
            body = trim_to_tokens(p["text"], remaining - token_len(header) - 5)
            lines.append(f"{header}\n{body}")
            used += token_len(header) + token_len(body)
            citations[tag] = f"{p['title']} ({p['source']}: {p['path']})"

        return {"context": "\n".join(lines), "citations": citations,
                "evidence_found": bool(facts or passages)}

    @staticmethod
    def route_after_fuse(state: AgentState) -> str:
        return "synthesize" if state.get("evidence_found") else "refuse"

    # ================================================================== #
    # Q5  Answer synthesis
    # ================================================================== #
    @timed("synthesize")
    def synthesize(self, state: AgentState) -> dict:
        prompt = prompts.SYNTHESIS_PROMPT.format(question=state["question"], context=state["context"])
        draft = self.d.llm.invoke(prompt).content.strip()
        return {"draft": draft}

    @staticmethod
    def route_after_synthesis(state: AgentState) -> str:
        return "refuse" if prompts.INSUFFICIENT_MARKER in state.get("draft", "") else "ground"

    # ================================================================== #
    # Q6  Grounding check
    # ================================================================== #
    @timed("ground")
    def ground(self, state: AgentState) -> dict:
        prompt = prompts.GROUNDING_PROMPT.format(context=state["context"], answer=state["draft"])
        try:
            claims = parse_json_object(self.d.judge_llm.invoke(prompt).content).get("claims", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("Grounding judge failed (%s); treating as ungrounded", exc)
            return {"grounding": {"claims": [], "supported": 0, "total": 0, "ratio": 0.0, "passed": False,
                                  "error": str(exc)}, "errors": [f"ground: {exc}"]}

        total = len(claims)
        supported = sum(1 for c in claims if c.get("supported") is True)
        ratio = supported / total if total else 0.0
        return {"grounding": {"claims": claims, "supported": supported, "total": total,
                              "ratio": round(ratio, 3), "passed": total > 0 and ratio >= self.d.grounding_threshold}}

    @staticmethod
    def route_after_grounding(state: AgentState) -> str:
        return "finalize" if state.get("grounding", {}).get("passed") else "refuse"

    # ================================================================== #
    # Q7a  Return answer      Q7b  Refusal
    # ================================================================== #
    @timed("finalize")
    def finalize(self, state: AgentState) -> dict:
        return {"answer": state["draft"], "status": "answered"}

    @timed("refuse")
    def refuse(self, state: AgentState) -> dict:
        if not state.get("evidence_found"):
            reason = "no evidence retrieved"
        elif prompts.INSUFFICIENT_MARKER in state.get("draft", ""):
            reason = "context did not contain the answer"
        else:
            g = state.get("grounding", {})
            reason = f"grounding check failed ({g.get('supported', 0)}/{g.get('total', 0)} claims supported)"
        # Log refusals so data gaps can be reviewed later
        log.info("REFUSED (%s): %s", reason, state.get("question"))
        return {"answer": prompts.REFUSAL_MESSAGE, "status": "refused", "refusal_reason": reason}
