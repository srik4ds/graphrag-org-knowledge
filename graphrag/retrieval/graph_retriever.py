"""
Box Q3A: graph retrieval.

Input : the template name chosen by the router + the linked entities.
Output: GraphResult with short natural-language facts, each later tagged [G1], [G2] ...

Decision order:
    1. Router picked a template and we have an entity of the right label -> run it.
    2. Otherwise, if Text2Cypher is enabled -> let the LLM write a read-only query.
    3. Otherwise (or if that returns nothing) -> 1-hop neighbourhood of each entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_neo4j import Neo4jGraph

from graphrag.retrieval.cypher_templates import TEMPLATES, CypherTemplate
from graphrag.retrieval.entity_linker import LinkedEntity
from graphrag.retrieval.text2cypher import Text2Cypher
from graphrag.utils import log


@dataclass
class GraphResult:
    facts: list[str] = field(default_factory=list)
    queries: list[dict] = field(default_factory=list)   # [{"cypher", "params", "row_count"}] for the UI
    strategy: str = "none"                              # "template:<name>", "text2cypher", "neighborhood"


def _format_generic_rows(rows: list[dict]) -> list[str]:
    """Fallback formatter for Text2Cypher results: 'key: value; key: value'."""
    return ["; ".join(f"{k}: {v}" for k, v in row.items() if v not in (None, [], "")) for row in rows]


class GraphRetriever:
    def __init__(self, graph: Neo4jGraph, text2cypher: Text2Cypher | None = None) -> None:
        self.graph = graph
        self.text2cypher = text2cypher

    # ------------------------------------------------------------------ #
    def retrieve(self, question: str, template_name: str | None, entities: list[LinkedEntity]) -> GraphResult:
        if not entities:
            return GraphResult(strategy="no entities")

        template = TEMPLATES.get(template_name or "")
        if template and template.name != "entity_neighborhood":
            entity = self._pick_entity(template, entities)
            if entity:
                result = self._run_template(template, entity)
                if result.facts:
                    return result
                log.info("Template %s returned no rows; falling back", template.name)

        if self.text2cypher is not None and template_name in (None, "", "none"):
            result = self._run_text2cypher(question, entities)
            if result.facts:
                return result

        return self._run_neighborhoods(entities)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _pick_entity(template: CypherTemplate, entities: list[LinkedEntity]) -> LinkedEntity | None:
        for e in entities:
            if template.entity_label in ("*", e.label):
                return e
        return None

    def _run_template(self, template: CypherTemplate, entity: LinkedEntity) -> GraphResult:
        params = {"id": entity.id}
        results, queries = [], []
        for cypher in template.statements:
            rows = self.graph.query(cypher, params)
            results.append(rows)
            queries.append({"cypher": cypher.strip(), "params": params, "row_count": len(rows)})
        return GraphResult(template.formatter(results), queries, f"template:{template.name}")

    def _run_text2cypher(self, question: str, entities: list[LinkedEntity]) -> GraphResult:
        cypher, rows = self.text2cypher.run(question, [e.as_dict() for e in entities])
        queries = [{"cypher": cypher, "params": {}, "row_count": len(rows)}] if cypher else []
        return GraphResult(_format_generic_rows(rows), queries, "text2cypher")

    def _run_neighborhoods(self, entities: list[LinkedEntity], max_entities: int = 2) -> GraphResult:
        template = TEMPLATES["entity_neighborhood"]
        merged = GraphResult(strategy="neighborhood")
        for entity in entities[:max_entities]:
            r = self._run_template(template, entity)
            merged.facts.extend(r.facts)
            merged.queries.extend(r.queries)
        return merged
