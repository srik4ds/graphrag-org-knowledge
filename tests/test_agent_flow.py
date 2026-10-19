"""
End-to-end LangGraph flow with fake dependencies (no Neo4j, no Nebius).

Checks the routing logic of the diagram:
    entities found  -> Q3A and Q3B both run  -> answer
    vector mode     -> Q3A skipped
    no evidence     -> Q7b refusal (from Q4)
    INSUFFICIENT    -> Q7b refusal (from Q5)
    ungrounded      -> Q7b refusal (from Q6)
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from graphrag.agent.builder import ask, build_graph
from graphrag.agent.nodes import AgentDeps
from graphrag.agent.prompts import REFUSAL_MESSAGE
from graphrag.retrieval.entity_linker import LinkedEntity
from graphrag.retrieval.graph_retriever import GraphResult
from graphrag.retrieval.hybrid_retriever import HybridResult, Passage


class FakeLLM:
    """Returns a scripted reply depending on which prompt it receives."""

    def __init__(self, router=None, synthesis="Sarah Jenkins moved to Project Triton [G1].", claims=None):
        self.router = router or {"mentions": [{"text": "Sarah Jenkins", "label": "Person"}],
                                 "template": "person_projects_tools", "reason": "test"}
        self.synthesis = synthesis
        self.claims = claims if claims is not None else [{"claim": "x", "citations": ["G1"], "supported": True}]
        self.calls = []

    def invoke(self, prompt: str):
        if "query router" in prompt:
            kind, reply = "router", json.dumps(self.router)
        elif "strict fact-checker" in prompt:
            kind, reply = "ground", json.dumps({"claims": self.claims})
        else:
            kind, reply = "synth", self.synthesis
        self.calls.append(kind)
        return SimpleNamespace(content=reply)


class FakeLinker:
    def link(self, mentions):
        return [LinkedEntity(m["text"], m["label"], "p_sjenkins", m["text"], "fulltext") for m in mentions]


class FakeGraphRetriever:
    def __init__(self, facts=("Sarah Jenkins worked on Project Triton.",)):
        self.facts, self.called = list(facts), False

    def retrieve(self, question, template, entities):
        self.called = True
        return GraphResult(self.facts, [{"cypher": "MATCH ...", "params": {}, "row_count": 1}], f"template:{template}")


class FakeHybrid:
    def __init__(self, passages=True):
        self.passages = passages

    def retrieve(self, question):
        if not self.passages:
            return HybridResult([], {})
        return HybridResult([Passage("doc::p0", "doc", "Project Triton", "wiki", "wiki/project_triton.md",
                                     "Sarah joined Triton in July.", 0.03, ["doc::p0::c0"], {"dense": 1})], {})


def make_agent(llm=None, graph=None, hybrid=None, linker=None):
    llm = llm or FakeLLM()
    deps = AgentDeps(llm=llm, judge_llm=llm, linker=linker or FakeLinker(),
                     graph_retriever=graph or FakeGraphRetriever(), hybrid_retriever=hybrid or FakeHybrid(),
                     today="2026-10-19")
    return build_graph(deps)


def test_graphrag_mode_runs_both_retrievers_in_parallel_and_answers():
    graph = FakeGraphRetriever()
    state = ask(make_agent(graph=graph), "What tools has Sarah used?", "graphrag")
    assert graph.called
    assert {"graph_retrieve", "vector_retrieve"} <= set(state["timings"])
    assert state["status"] == "answered"
    assert "[G1]" in state["context"] and "[V1]" in state["context"]


def test_vector_mode_skips_graph_and_router_llm():
    llm, graph = FakeLLM(), FakeGraphRetriever()
    state = ask(make_agent(llm=llm, graph=graph), "What tools has Sarah used?", "vector")
    assert not graph.called and "router" not in llm.calls
    assert "graph_retrieve" not in state["timings"]
    assert state["status"] == "answered"


def test_no_entities_means_vector_only():
    llm = FakeLLM(router={"mentions": [], "template": "none", "reason": "general"})
    graph = FakeGraphRetriever()
    state = ask(make_agent(llm=llm, graph=graph), "How do we run on-call?", "graphrag")
    assert not graph.called and state["run_graph"] is False


def test_no_evidence_refuses_before_calling_the_llm():
    llm = FakeLLM(router={"mentions": [], "template": "none", "reason": "x"})
    state = ask(make_agent(llm=llm, hybrid=FakeHybrid(passages=False)), "Unknown topic?", "graphrag")
    assert state["status"] == "refused" and state["answer"] == REFUSAL_MESSAGE
    assert "synth" not in llm.calls


def test_insufficient_context_refuses():
    state = ask(make_agent(llm=FakeLLM(synthesis="INSUFFICIENT_CONTEXT")), "Q?", "graphrag")
    assert state["status"] == "refused" and "did not contain" in state["refusal_reason"]


def test_ungrounded_answer_refuses():
    claims = [{"claim": "a", "supported": True}, {"claim": "b", "supported": False}, {"claim": "c", "supported": False}]
    state = ask(make_agent(llm=FakeLLM(claims=claims)), "Q?", "graphrag")
    assert state["status"] == "refused" and "1/3" in state["refusal_reason"]


def test_router_bad_json_degrades_to_vector_only():
    class BadRouterLLM(FakeLLM):
        def invoke(self, prompt):
            if "query router" in prompt:
                return SimpleNamespace(content="sorry, no json")
            return super().invoke(prompt)

    state = ask(make_agent(llm=BadRouterLLM()), "Q?", "graphrag")
    assert state["run_graph"] is False and state["status"] == "answered" and state["errors"]
