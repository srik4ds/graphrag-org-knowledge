"""
Box Q2 (second half): entity linking.

The router LLM reads the question and returns MENTIONS such as

    {"text": "the last compliance audit", "label": "Project", "category": "audit", "temporal": "latest"}
    {"text": "Alex Chen", "label": "Person"}

This module turns each mention into a concrete graph node id:

    temporal = "latest"   -> Cypher: newest node of that label (and category)
    otherwise             -> full-text search over names + aliases, fuzzy (typos ok)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from langchain_neo4j import Neo4jGraph

from graphrag import schema
from graphrag.utils import log, to_lucene_keywords


@dataclass
class LinkedEntity:
    mention: str
    label: str
    id: str
    name: str
    method: str          # "latest" or "fulltext"
    score: float = 1.0

    def as_dict(self) -> dict:
        return asdict(self)


# "Latest" queries per label. Dates are ISO strings, so text ordering works.
_LATEST_QUERIES = {
    "Project": """
        MATCH (n:Project)
        WHERE ($category IS NULL OR n.category = $category)
          AND n.end_date IS NOT NULL AND n.end_date <= $today
        RETURN n.id AS id, n.name AS name ORDER BY n.end_date DESC LIMIT 1""",
    "Incident": """
        MATCH (n:Incident) WHERE n.created <= $today
        RETURN n.id AS id, n.name AS name ORDER BY n.created DESC LIMIT 1""",
    "Decision": """
        MATCH (n:Decision) WHERE n.date <= $today
        RETURN n.id AS id, n.name AS name ORDER BY n.date DESC LIMIT 1""",
    "Release": """
        MATCH (n:Release) WHERE n.target_date >= $today
        RETURN n.id AS id, n.name AS name ORDER BY n.target_date ASC LIMIT 1""",
}

_FULLTEXT_QUERY = f"""
CALL db.index.fulltext.queryNodes('{schema.ENTITY_FULLTEXT_INDEX}', $q) YIELD node, score
WITH node, score WHERE $label IS NULL OR $label IN labels(node)
RETURN node.id AS id, node.name AS name, labels(node)[0] AS label, score
ORDER BY score DESC LIMIT 3
"""


class EntityLinker:
    def __init__(self, graph: Neo4jGraph, today: str) -> None:
        self.graph = graph
        self.today = today

    def link(self, mentions: list[dict]) -> list[LinkedEntity]:
        """Link every mention; mentions that match nothing are dropped (and logged)."""
        linked: list[LinkedEntity] = []
        for m in mentions:
            entity = self._link_one(m)
            if entity:
                linked.append(entity)
            else:
                log.info("Entity linker: no match for %r", m)
        # de-duplicate by id, keeping the first occurrence
        unique = {e.id: e for e in reversed(linked)}
        return [e for e in linked if unique.get(e.id) is e]

    def _link_one(self, m: dict) -> LinkedEntity | None:
        text = (m.get("text") or "").strip()
        label = m.get("label") if m.get("label") in schema.ENTITY_LABELS else None

        # 1. Temporal mentions: "the last audit", "the most recent incident"
        if m.get("temporal") in {"latest", "most_recent", "last", "next"} and label in _LATEST_QUERIES:
            rows = self.graph.query(_LATEST_QUERIES[label], {"category": m.get("category"), "today": self.today})
            if rows:
                return LinkedEntity(text, label, rows[0]["id"], rows[0]["name"], "latest")

        # 2. Name lookup: full-text with fuzzy matching, first with the label, then without
        if not text:
            return None
        query = to_lucene_keywords(text, fuzzy=True)
        for label_filter in ([label, None] if label else [None]):
            rows = self.graph.query(_FULLTEXT_QUERY, {"q": query, "label": label_filter})
            if rows:
                r = rows[0]
                return LinkedEntity(text, r["label"], r["id"], r["name"], "fulltext", float(r["score"]))
        return None
