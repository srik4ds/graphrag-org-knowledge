"""
Box Q3B: hybrid vector retrieval.

Steps
    1. Dense search   : embed the question, top-k children from the vector index
    2. BM25 search    : keywords of the question, top-k children from the full-text index
    3. RRF merge      : 1/(60 + dense_rank) + 1/(60 + bm25_rank)
    4. Rerank (opt.)  : LLM reorders the top candidates (RERANK_MODE=llm)
    5. Parents        : swap the best children for their 1024-token parents (deduplicated)

Output passages are later tagged [V1], [V2] ... in the context.

We call the two Neo4j indexes directly (instead of Neo4jVector's built-in hybrid
mode) so every step, including RRF, is visible and easy to explain in the demo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_neo4j import Neo4jGraph

from graphrag import schema
from graphrag.agent.prompts import RERANK_PROMPT
from graphrag.config import Settings
from graphrag.retrieval.rrf import FusedItem, reciprocal_rank_fusion
from graphrag.utils import log, parse_json_object, to_lucene_keywords

_DENSE_QUERY = f"""
CALL db.index.vector.queryNodes('{schema.CHUNK_VECTOR_INDEX}', $k, $embedding) YIELD node, score
RETURN node.id AS id, node.parent_id AS parent_id, node.text AS text, score
"""

_BM25_QUERY = f"""
CALL db.index.fulltext.queryNodes('{schema.CHUNK_FULLTEXT_INDEX}', $q, {{limit: $k}}) YIELD node, score
RETURN node.id AS id, node.parent_id AS parent_id, node.text AS text, score
"""

_PARENTS_QUERY = """
UNWIND $ids AS pid
MATCH (p:Parent {id: pid})-[:PART_OF]->(d:Document)
RETURN p.id AS parent_id, p.text AS text, d.id AS doc_id, d.name AS title, d.source AS source, d.path AS path
"""


@dataclass
class Passage:
    parent_id: str
    doc_id: str
    title: str
    source: str
    path: str
    text: str
    rrf_score: float
    child_ids: list[str] = field(default_factory=list)
    ranks: dict[str, int] = field(default_factory=dict)


@dataclass
class HybridResult:
    passages: list[Passage] = field(default_factory=list)
    debug: dict = field(default_factory=dict)


class HybridRetriever:
    def __init__(self, graph: Neo4jGraph, embeddings: Embeddings, settings: Settings,
                 rerank_llm: BaseChatModel | None = None) -> None:
        self.graph = graph
        self.embeddings = embeddings
        self.s = settings
        self.rerank_llm = rerank_llm if settings.rerank_mode == "llm" else None

    # ------------------------------------------------------------------ #
    def retrieve(self, question: str) -> HybridResult:
        # 1. dense
        vector = self.embeddings.embed_query(question)
        dense = self.graph.query(_DENSE_QUERY, {"k": self.s.dense_top_k, "embedding": vector})

        # 2. BM25 (empty keyword query would be a Lucene syntax error, so guard it)
        keywords = to_lucene_keywords(question)
        bm25 = self.graph.query(_BM25_QUERY, {"q": keywords, "k": self.s.bm25_top_k}) if keywords.strip() else []

        # 3. RRF
        fused = reciprocal_rank_fusion({"dense": [r["id"] for r in dense], "bm25": [r["id"] for r in bm25]},
                                       k=self.s.rrf_k)
        children = {r["id"]: r for r in dense + bm25}

        # 4. optional rerank of the top candidates
        candidates = fused[: max(self.s.final_child_top_k * 2, 10)]
        if self.rerank_llm is not None:
            candidates = self._rerank(question, candidates, children)
        top = candidates[: self.s.final_child_top_k]

        # 5. children -> parents (keep order, merge children of the same parent)
        passages = self._to_parents(top, children)

        debug = {
            "keywords": keywords,
            "dense": [(r["id"], round(r["score"], 4)) for r in dense[:10]],
            "bm25": [(r["id"], round(r["score"], 3)) for r in bm25[:10]],
            "fused": [(f.id, round(f.score, 5), f.ranks) for f in fused[:10]],
        }
        return HybridResult(passages, debug)

    # ------------------------------------------------------------------ #
    def _to_parents(self, top: list[FusedItem], children: dict[str, dict]) -> list[Passage]:
        order: list[str] = []
        by_parent: dict[str, list[FusedItem]] = {}
        for item in top:
            pid = children[item.id]["parent_id"]
            if pid not in by_parent:
                order.append(pid)
                by_parent[pid] = []
            by_parent[pid].append(item)

        rows = {r["parent_id"]: r for r in self.graph.query(_PARENTS_QUERY, {"ids": order})}
        passages = []
        for pid in order:
            if pid not in rows:
                continue
            r, items = rows[pid], by_parent[pid]
            passages.append(Passage(
                parent_id=pid, doc_id=r["doc_id"], title=r["title"], source=r["source"], path=r["path"],
                text=r["text"], rrf_score=max(i.score for i in items),
                child_ids=[i.id for i in items], ranks=items[0].ranks))
        return passages

    def _rerank(self, question: str, candidates: list[FusedItem], children: dict[str, dict]) -> list[FusedItem]:
        """Ask the LLM to order candidates by usefulness. Falls back to RRF order on any error."""
        listing = "\n".join(f"[{i}] {children[c.id]['text'][:500]}" for i, c in enumerate(candidates))
        try:
            reply = self.rerank_llm.invoke(RERANK_PROMPT.format(question=question, candidates=listing)).content
            order = [int(i) for i in parse_json_object(reply).get("order", []) if 0 <= int(i) < len(candidates)]
            seen = set(order)
            return [candidates[i] for i in order] + [c for i, c in enumerate(candidates) if i not in seen]
        except Exception as exc:  # noqa: BLE001
            log.warning("Rerank failed (%s); keeping RRF order", exc)
            return candidates
