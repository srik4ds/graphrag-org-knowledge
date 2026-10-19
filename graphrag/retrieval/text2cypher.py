"""
Box Q3A fallback: Text2Cypher.

When the router finds entities but no template fits, the LLM writes a Cypher query
from the schema. Generated Cypher is never trusted blindly:

    1. Only read clauses are allowed (no CREATE, MERGE, DELETE, SET, REMOVE, DROP,
       LOAD CSV, or procedure calls that write).
    2. A LIMIT is appended if missing.
    3. Errors are caught; the pipeline then simply has no graph facts.

(LangChain's GraphCypherQAChain does the same generate-and-run loop; we keep our
own small version so the read-only guard is explicit and easy to explain.)
"""

from __future__ import annotations

import re

from langchain_core.language_models import BaseChatModel
from langchain_neo4j import Neo4jGraph

from graphrag.agent.prompts import TEXT2CYPHER_PROMPT
from graphrag.schema import SCHEMA_DESCRIPTION
from graphrag.utils import log

_WRITE_CLAUSES = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|CALL\s+dbms|CALL\s+apoc\.(create|merge|refactor|periodic))\b",
    re.IGNORECASE,
)


def extract_cypher(llm_text: str) -> str:
    """Pull the query out of ```cypher fences if the model added them."""
    fenced = re.search(r"```(?:cypher)?\s*(.*?)```", llm_text, re.DOTALL | re.IGNORECASE)
    return (fenced.group(1) if fenced else llm_text).strip().rstrip(";")


def is_read_only(cypher: str) -> bool:
    return not _WRITE_CLAUSES.search(cypher)


def ensure_limit(cypher: str, limit: int = 50) -> str:
    return cypher if re.search(r"\bLIMIT\s+\d+", cypher, re.IGNORECASE) else f"{cypher}\nLIMIT {limit}"


class Text2Cypher:
    def __init__(self, graph: Neo4jGraph, llm: BaseChatModel) -> None:
        self.graph = graph
        self.llm = llm

    def run(self, question: str, entities: list[dict]) -> tuple[str | None, list[dict]]:
        """Return (cypher, rows). On any problem returns (cypher_or_None, [])."""
        prompt = TEXT2CYPHER_PROMPT.format(schema=SCHEMA_DESCRIPTION, question=question,
                                           entities="\n".join(f"- {e['name']} ({e['label']}, id={e['id']})" for e in entities) or "none")
        cypher = extract_cypher(self.llm.invoke(prompt).content)
        if not is_read_only(cypher):
            log.warning("Text2Cypher produced a write query; refusing to run it:\n%s", cypher)
            return cypher, []
        cypher = ensure_limit(cypher)
        try:
            return cypher, self.graph.query(cypher)
        except Exception as exc:  # noqa: BLE001  (bad generated Cypher must not crash the app)
            log.warning("Text2Cypher query failed: %s", exc)
            return cypher, []
