"""Tests for RRF (Q3B), the Text2Cypher read-only guard (Q3A) and helpers."""

import pytest

from graphrag.retrieval.rrf import reciprocal_rank_fusion
from graphrag.retrieval.text2cypher import ensure_limit, extract_cypher, is_read_only
from graphrag.utils import parse_json_object, to_lucene_keywords


def test_rrf_worked_example_from_the_design_notes():
    # chunk A: dense #1, BM25 #3 | chunk B: dense #2 only | chunk C: dense #4, BM25 #1 | chunk D: BM25 #2 only
    fused = reciprocal_rank_fusion({"dense": ["A", "B", "x", "C"], "bm25": ["C", "D", "A"]}, k=60)
    scores = {f.id: f.score for f in fused}
    assert scores["A"] == pytest.approx(1 / 61 + 1 / 63)      # 0.0323
    assert scores["C"] == pytest.approx(1 / 64 + 1 / 61)      # 0.0320
    assert scores["B"] == pytest.approx(1 / 62)               # 0.0161
    assert [f.id for f in fused[:2]] == ["A", "C"]            # agreement wins
    assert fused[0].ranks == {"dense": 1, "bm25": 3}


@pytest.mark.parametrize("cypher", [
    "MATCH (n) DETACH DELETE n",
    "MATCH (p:Person) SET p.name = 'x' RETURN p",
    "CREATE (n:Person {id: 'evil'})",
    "MERGE (n:Person {id: 'x'})",
    "CALL apoc.create.node(['X'], {})",
])
def test_write_queries_are_rejected(cypher):
    assert not is_read_only(cypher)


def test_read_query_is_allowed_and_gets_a_limit():
    q = "MATCH (p:Person)-[:MEMBER_OF]->(t:Team) RETURN p.name, t.name"
    assert is_read_only(q)
    assert ensure_limit(q).endswith("LIMIT 50")


def test_cypher_is_extracted_from_fences():
    assert extract_cypher("```cypher\nMATCH (n) RETURN n.name;\n```") == "MATCH (n) RETURN n.name"


def test_json_is_parsed_from_chatty_llm_output():
    text = 'Sure! Here it is:\n```json\n{"template": "release_blockers", "mentions": []}\n```'
    assert parse_json_object(text)["template"] == "release_blockers"


def test_lucene_keywords_drop_stopwords_and_escape():
    q = to_lucene_keywords("Who owns ledger-db?")
    assert "Who" not in q and "ledger\\-db" in q
