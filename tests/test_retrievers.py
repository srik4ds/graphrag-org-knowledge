"""
Retriever and writer logic with a fake Neo4j connection that returns canned rows.
(Cypher itself is exercised against the real database by ask.py / evaluate.py.)
"""

from __future__ import annotations

from types import SimpleNamespace

from graphrag.ingest.graph_writer import GraphWriter
from graphrag.ingest.models import Edge, Node
from graphrag.retrieval.cypher_templates import TEMPLATES
from graphrag.retrieval.entity_linker import EntityLinker, LinkedEntity
from graphrag.retrieval.graph_retriever import GraphRetriever
from graphrag.retrieval.hybrid_retriever import HybridRetriever


class FakeGraph:
    """Records every query; answers with the first canned response whose key appears in the Cypher."""

    def __init__(self, responses: dict[str, list] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    def query(self, cypher: str, params: dict | None = None):
        self.calls.append((cypher, params or {}))
        for key, rows in self.responses.items():
            if key in cypher:
                return rows
        return []


def test_template_formatter_for_release_blockers():
    rows = [{"release": "Triton GA", "target_date": "2026-12-10", "ticket": "TRI-8", "summary": "EKS", "status": "Done",
             "priority": "High", "assignee": "Sarah Jenkins"},
            {"release": "Triton GA", "target_date": "2026-12-10", "ticket": "TRI-12", "summary": "Migrate", "status": "In Progress",
             "priority": "Highest", "assignee": "Alex Chen"}]
    facts = TEMPLATES["release_blockers"].formatter([rows])
    assert "closed, no longer blocking" in facts[0] and "open" in facts[1]


def test_graph_retriever_runs_template_with_entity_id():
    graph = FakeGraph({"(r:Release {id: $id})": [{"release": "Triton GA", "target_date": "x", "ticket": "TRI-12",
                                                  "summary": "s", "status": "Open", "priority": "High", "assignee": "Alex Chen"}]})
    result = GraphRetriever(graph).retrieve("q", "release_blockers",
                                            [LinkedEntity("Triton GA", "Release", "rel_triton_ga", "Triton GA", "fulltext")])
    assert result.strategy == "template:release_blockers"
    assert graph.calls[0][1] == {"id": "rel_triton_ga"} and "TRI-12" in result.facts[0]


def test_graph_retriever_falls_back_to_neighborhood_when_label_mismatch():
    graph = FakeGraph({"MATCH (n {id: $id})-[r]-(m)": [{"entity": "Alex Chen", "rel": "OWNS", "outgoing": True,
                                                       "neighbor": "ledger-db", "neighbor_label": "Service", "rel_props": {}}]})
    result = GraphRetriever(graph).retrieve("q", "release_blockers",
                                            [LinkedEntity("Alex", "Person", "p_achen", "Alex Chen", "fulltext")])
    assert result.strategy == "neighborhood" and "Alex Chen -[OWNS]-> ledger-db" in result.facts[0]


def test_entity_linker_uses_latest_query_for_temporal_mentions():
    graph = FakeGraph({"ORDER BY n.end_date DESC": [{"id": "proj_q2_sox_audit", "name": "Q2 2026 SOX Audit"}]})
    linked = EntityLinker(graph, "2026-10-19").link(
        [{"text": "the last compliance audit", "label": "Project", "category": "audit", "temporal": "latest"}])
    assert linked[0].id == "proj_q2_sox_audit" and linked[0].method == "latest"
    assert graph.calls[0][1] == {"category": "audit", "today": "2026-10-19"}


def test_entity_linker_fuzzy_fulltext_for_names():
    graph = FakeGraph({"db.index.fulltext.queryNodes": [{"id": "proj_triton", "name": "Project Triton",
                                                         "label": "Project", "score": 2.1}]})
    linked = EntityLinker(graph, "2026-10-19").link([{"text": "Trtion", "label": "Project"}])
    assert linked[0].id == "proj_triton"
    assert "Trtion~" in graph.calls[0][1]["q"]                 # fuzzy operator added


def test_hybrid_retriever_rrf_and_parent_swap(settings):
    dense = [{"id": "d::p0::c0", "parent_id": "d::p0", "text": "a", "score": 0.9},
             {"id": "d::p0::c1", "parent_id": "d::p0", "text": "b", "score": 0.8},
             {"id": "e::p0::c0", "parent_id": "e::p0", "text": "c", "score": 0.7}]
    bm25 = [{"id": "e::p0::c0", "parent_id": "e::p0", "text": "c", "score": 5.0}]
    parents = [{"parent_id": "d::p0", "text": "parent d", "doc_id": "d", "title": "Doc D", "source": "wiki", "path": "wiki/d.md"},
               {"parent_id": "e::p0", "text": "parent e", "doc_id": "e", "title": "Doc E", "source": "slack", "path": "comms/e.json"}]
    graph = FakeGraph({"db.index.vector.queryNodes": dense, "db.index.fulltext.queryNodes": bm25, "UNWIND $ids": parents})
    emb = SimpleNamespace(embed_query=lambda q: [0.1, 0.2])
    result = HybridRetriever(graph, emb, settings).retrieve("Who owns ledger-db?")
    # e::p0::c0 is in both lists, so its parent ranks first; d's two children merge into one passage
    assert [p.parent_id for p in result.passages] == ["e::p0", "d::p0"]
    assert result.passages[1].child_ids == ["d::p0::c0", "d::p0::c1"]


def test_graph_writer_groups_by_label_and_rejects_unknown_labels():
    graph = FakeGraph({"RETURN count(r) AS n": [{"n": 1}]})
    writer = GraphWriter(graph)
    writer.write_nodes([Node("Person", "p1", {"name": "A"}), Node("Team", "t1", {"name": "T"})])
    writer.write_edges([Edge("Person", "p1", "MEMBER_OF", "Team", "t1")])
    assert any("MERGE (n:Person" in c for c, _ in graph.calls) and any("[r:MEMBER_OF]" in c for c, _ in graph.calls)
    try:
        writer.write_nodes([Node("Hacker; DROP", "x")])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
