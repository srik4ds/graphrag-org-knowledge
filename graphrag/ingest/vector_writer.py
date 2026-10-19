"""
Box 5B -> 6B: embed child chunks and store them in Neo4j.

Storage layout (one database, linked to the graph):

    (:Chunk {id, text, embedding, parent_id, doc_id, source})
        -[:CHILD_OF]->  (:Parent {id, text, doc_id})
                            -[:PART_OF]-> (:Document)
    (:Chunk)-[:MENTIONS]->(:Person | :Project | :Service | ...)

Indexes:
    chunk_embedding   vector index (cosine) on Chunk.embedding  -> dense search
    chunk_text        full-text index on Chunk.text             -> BM25 keyword search
"""

from __future__ import annotations

from collections import defaultdict

from langchain_core.embeddings import Embeddings
from langchain_neo4j import Neo4jGraph

from graphrag import schema
from graphrag.ingest.models import ChildChunk, ParentChunk
from graphrag.utils import log

WRITE_BATCH = 100


class VectorWriter:
    def __init__(self, graph: Neo4jGraph, embeddings: Embeddings, embed_batch_size: int = 32) -> None:
        self.graph = graph
        self.embeddings = embeddings
        self.embed_batch_size = embed_batch_size

    # ------------------------------------------------------------------ #
    # Indexes
    # ------------------------------------------------------------------ #
    def detect_dimensions(self) -> int:
        """Embed a probe string once to learn the model's vector size."""
        dims = len(self.embeddings.embed_query("dimension probe"))
        log.info("Embedding model returns %d-dimensional vectors", dims)
        return dims

    def create_indexes(self, dimensions: int) -> None:
        self.graph.query(schema.chunk_vector_statement(dimensions))
        self.graph.query(schema.chunk_fulltext_statement())
        self.graph.query("CALL db.awaitIndexes(300)")          # wait until indexes are ONLINE
        log.info("Vector and full-text indexes ready")

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def write_parents(self, parents: list[ParentChunk]) -> None:
        rows = [{"id": p.id, "doc_id": p.doc_id, "text": p.text, "position": p.position} for p in parents]
        self.graph.query(
            "UNWIND $rows AS row "
            "MERGE (p:Parent {id: row.id}) "
            "SET p.text = row.text, p.doc_id = row.doc_id, p.position = row.position "
            "WITH p, row MATCH (d:Document {id: row.doc_id}) "
            "MERGE (p)-[:PART_OF]->(d)",
            {"rows": rows},
        )
        log.info("  wrote %d Parent chunks", len(rows))

    def write_children(self, children: list[ChildChunk], source_by_doc: dict[str, str]) -> None:
        """Embed children in batches and write them with their vectors."""
        for start in range(0, len(children), self.embed_batch_size):
            batch = children[start:start + self.embed_batch_size]
            vectors = self.embeddings.embed_documents([c.text for c in batch])
            rows = [{
                "id": c.id, "text": c.text, "parent_id": c.parent_id, "doc_id": c.doc_id,
                "position": c.position, "source": source_by_doc.get(c.doc_id, "unknown"),
                "embedding": vec,
            } for c, vec in zip(batch, vectors)]
            self.graph.query(
                "UNWIND $rows AS row "
                "MERGE (c:Chunk {id: row.id}) "
                "SET c.text = row.text, c.parent_id = row.parent_id, c.doc_id = row.doc_id, "
                "    c.position = row.position, c.source = row.source, c.embedding = row.embedding "
                "WITH c, row MATCH (p:Parent {id: row.parent_id}) "
                "MERGE (c)-[:CHILD_OF]->(p)",
                {"rows": rows},
            )
            log.info("  embedded and wrote chunks %d-%d of %d", start + 1, start + len(batch), len(children))

    def write_mentions(self, children: list[ChildChunk]) -> None:
        """(:Chunk)-[:MENTIONS]->(entity): the bridge between the vector side and the graph."""
        by_label: dict[str, list[dict]] = defaultdict(list)
        for c in children:
            for label, entity_id in c.mentions:
                by_label[label].append({"chunk": c.id, "entity": entity_id})
        for label, rows in by_label.items():
            if label not in schema.ENTITY_LABELS:
                continue
            self.graph.query(
                f"UNWIND $rows AS row "
                f"MATCH (c:Chunk {{id: row.chunk}}) MATCH (e:{label} {{id: row.entity}}) "
                f"MERGE (c)-[:MENTIONS]->(e)",
                {"rows": rows},
            )
            log.info("  wrote %d MENTIONS -> %s", len(rows), label)
