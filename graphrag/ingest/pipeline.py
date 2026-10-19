"""
Ingestion orchestrator: runs boxes 1A to 6B in order.

Split into two functions on purpose:

    prepare(settings)     pure Python, no network. Loads, cleans, resolves, extracts
                          and chunks everything. Safe to run offline and in tests.
    run_ingest(settings)  calls prepare(), then writes the graph (6A) and the
                          embedded chunks (6B) to Neo4j.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from graphrag.config import Settings
from graphrag.ingest import cleaners, graph_extractors as gx, loaders
from graphrag.ingest.chunker import ParentChildChunker
from graphrag.ingest.entity_resolver import EntityRegistry
from graphrag.ingest.models import ChildChunk, GraphBatch, ParentChunk, TextDocument
from graphrag.utils import log


@dataclass
class PreparedData:
    registry: EntityRegistry
    graph: GraphBatch
    text_docs: list[TextDocument]
    parents: list[ParentChunk]
    children: list[ChildChunk]
    stats: dict = field(default_factory=dict)


def prepare(settings: Settings) -> PreparedData:
    """Everything up to (but not including) database writes."""
    root = settings.data_dir

    # ---- 1A-1D: load -------------------------------------------------------
    directory = loaders.load_directory(settings.directory_file)
    pages = loaders.load_wiki(settings.wiki_dir, root)
    issues = loaders.load_jira(settings.issues_dir, root)
    channels = loaders.load_slack(settings.comms_dir, root)

    # ---- 3: entity registry (pass 1) ---------------------------------------
    registry = gx.build_registry(directory, pages, issues)
    log.info("Entity registry: %d entities", len(registry))

    # ---- 2C: Slack threads (vector only) -----------------------------------
    slack_docs = [doc for ch in channels for doc in cleaners.slack_threads_to_documents(ch, registry)]

    # ---- 4A: graph extraction (pass 2) -------------------------------------
    graph = (
        gx.extract_directory(directory, registry)
        + gx.extract_wiki(pages, registry)
        + gx.extract_jira(issues, registry)
        + gx.tool_nodes(registry)
        + gx.slack_document_nodes(slack_docs, registry)
    )
    for problem in graph.unresolved:
        log.warning("Unresolved reference -> %s", problem)

    # ---- 2B: wiki bodies (vector side) -------------------------------------
    wiki_docs = [cleaners.wiki_to_text_document(p, gx.wiki_doc_id(p), registry) for p in pages]
    text_docs = wiki_docs + slack_docs

    # ---- 4B: parent-child chunking -----------------------------------------
    chunker = ParentChildChunker(settings.parent_chunk_tokens, settings.child_chunk_tokens,
                                 settings.child_chunk_overlap, registry)
    parents, children = chunker.split_all(text_docs)

    stats = {
        "people": len(directory["people"]), "wiki_pages": len(pages), "jira_issues": len(issues),
        "slack_threads": len(slack_docs), "graph_nodes": len(graph.nodes), "graph_edges": len(graph.edges),
        "unresolved_refs": len(graph.unresolved), "text_documents": len(text_docs),
        "parent_chunks": len(parents), "child_chunks": len(children),
        "chunk_mentions": sum(len(c.mentions) for c in children),
    }
    log.info("Prepared: %s", stats)
    return PreparedData(registry, graph, text_docs, parents, children, stats)


def run_ingest(settings: Settings, reset: bool = False, skip_vectors: bool = False) -> dict:
    """Prepare everything, then write to Neo4j (graph first, vectors second)."""
    # Imported here so `prepare()` works without Neo4j or Nebius credentials
    from graphrag.clients import get_embeddings, get_graph
    from graphrag.ingest.graph_writer import GraphWriter
    from graphrag.ingest.vector_writer import VectorWriter

    data = prepare(settings)
    graph = get_graph(settings)
    writer = GraphWriter(graph)

    if reset:
        writer.reset_database()
    writer.create_constraints_and_indexes()

    # ---- 6A: knowledge graph -------------------------------------------------
    log.info("Writing knowledge graph ...")
    graph_counts = writer.write_batch(data.graph)

    # ---- 5B -> 6B: chunk store -----------------------------------------------
    if not skip_vectors:
        log.info("Embedding and writing chunks ...")
        vw = VectorWriter(graph, get_embeddings(settings), settings.embed_batch_size)
        vw.create_indexes(vw.detect_dimensions())
        source_by_doc = {d.doc_id: d.source for d in data.text_docs}
        vw.write_parents(data.parents)
        vw.write_children(data.children, source_by_doc)
        vw.write_mentions(data.children)

    summary = {**data.stats, **{f"written_{k}": v for k, v in graph_counts.items()}}
    log.info("Ingest complete: %s", summary)
    return summary
