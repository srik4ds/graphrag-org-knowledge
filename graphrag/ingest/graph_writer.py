"""
Box 4A (part 2) -> 6A: write nodes and edges to Neo4j.

Every write uses MERGE on the node id, so running ingest twice updates nodes in
place instead of duplicating them (idempotent ingestion).

Labels and relationship types cannot be passed as Cypher parameters, so they are
inserted into the query text. To stay safe we only allow names declared in
graphrag/schema.py.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from langchain_neo4j import Neo4jGraph

from graphrag import schema
from graphrag.ingest.models import Edge, GraphBatch, Node
from graphrag.utils import log

BATCH_SIZE = 500


def _check_label(label: str) -> str:
    if label not in schema.ALL_LABELS:
        raise ValueError(f"Unknown label {label!r}; add it to graphrag/schema.py first")
    return label


def _check_rel(rel: str) -> str:
    if rel not in schema.REL_TYPES:
        raise ValueError(f"Unknown relationship type {rel!r}; add it to graphrag/schema.py first")
    return rel


def _chunks(items: list, size: int = BATCH_SIZE) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


class GraphWriter:
    """Thin wrapper around Neo4jGraph.query for bulk, idempotent writes."""

    def __init__(self, graph: Neo4jGraph) -> None:
        self.graph = graph

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def reset_database(self) -> None:
        """Delete everything. Used by `python ingest.py --reset`."""
        log.warning("Deleting all nodes and relationships")
        # The demo graph is small (a few thousand nodes), so one statement is fine.
        self.graph.query("MATCH (n) DETACH DELETE n")
        # Drop the vector index too: its dimension is tied to the embedding model,
        # and a model change would otherwise leave a mismatched index behind.
        self.graph.query(f"DROP INDEX {schema.CHUNK_VECTOR_INDEX} IF EXISTS")

    def create_constraints_and_indexes(self) -> None:
        """Uniqueness constraints per label + the entity-name full-text index."""
        for stmt in schema.constraint_statements():
            self.graph.query(stmt)
        self.graph.query(schema.entity_fulltext_statement())
        log.info("Constraints and entity full-text index ready")

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def write_nodes(self, nodes: list[Node]) -> int:
        """MERGE nodes by (label, id) and set their properties."""
        by_label: dict[str, list[dict]] = defaultdict(list)
        for n in nodes:
            by_label[_check_label(n.label)].append({"id": n.id, "props": n.props})

        for label, rows in by_label.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MERGE (n:{label} {{id: row.id}}) "
                f"SET n += row.props"
            )
            for part in _chunks(rows):
                self.graph.query(cypher, {"rows": part})
            log.info("  wrote %4d %s nodes", len(rows), label)
        return len(nodes)

    def write_edges(self, edges: list[Edge]) -> int:
        """
        MERGE relationships between existing nodes.
        Edges whose endpoints do not exist are skipped (and counted) instead of
        creating empty placeholder nodes.
        """
        groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for e in edges:
            key = (_check_label(e.src_label), _check_rel(e.rel), _check_label(e.dst_label))
            groups[key].append({"src": e.src_id, "dst": e.dst_id, "props": e.props})

        written = 0
        for (src_label, rel, dst_label), rows in groups.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MATCH (a:{src_label} {{id: row.src}}) "
                f"MATCH (b:{dst_label} {{id: row.dst}}) "
                f"MERGE (a)-[r:{rel}]->(b) "
                f"SET r += row.props "
                f"RETURN count(r) AS n"
            )
            for part in _chunks(rows):
                result = self.graph.query(cypher, {"rows": part})
                written += result[0]["n"] if result else 0
            log.info("  wrote %4d (:%s)-[:%s]->(:%s)", len(rows), src_label, rel, dst_label)

        if written < len(edges):
            log.warning("%d edges skipped because an endpoint node was missing", len(edges) - written)
        return written

    def write_batch(self, batch: GraphBatch) -> dict:
        """Nodes first, then edges (edges need both endpoints to exist)."""
        n = self.write_nodes(batch.nodes)
        e = self.write_edges(batch.edges)
        return {"nodes": n, "edges": e}
