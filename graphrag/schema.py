"""
Graph schema: the single source of truth for labels, relationship types,
constraints and indexes.

The same schema text (SCHEMA_DESCRIPTION) is shown to the LLM in the router and in
the Text2Cypher fallback, so the model and the database agree on names.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Node labels
# --------------------------------------------------------------------------- #
# "Entity" labels: things people ask about. Each has a unique `id` and a `name`.
ENTITY_LABELS: tuple[str, ...] = (
    "Person", "Team", "Project", "Service", "Tool",
    "Release", "Decision", "Incident", "Ticket", "Document",
)

# Text storage labels for the vector side (box 6B)
TEXT_LABELS: tuple[str, ...] = ("Parent", "Chunk")

ALL_LABELS: tuple[str, ...] = ENTITY_LABELS + TEXT_LABELS

# --------------------------------------------------------------------------- #
# Relationship types  (source label, TYPE, target label)
# --------------------------------------------------------------------------- #
RELATIONSHIPS: tuple[tuple[str, str, str], ...] = (
    ("Person",   "MEMBER_OF",   "Team"),
    ("Person",   "WORKED_ON",   "Project"),     # props: role, start_date, end_date
    ("Project",  "OWNED_BY",    "Team"),
    ("Project",  "USES",        "Tool"),
    ("Service",  "USES",        "Tool"),
    ("Team",     "OWNS",        "Service"),
    ("Person",   "OWNS",        "Service"),     # primary owner
    ("Service",  "DEPENDS_ON",  "Service"),
    ("Release",  "DEPENDS_ON",  "Service"),
    ("Release",  "PART_OF",     "Project"),
    ("Ticket",   "PART_OF",     "Project"),
    ("Ticket",   "ASSIGNED_TO", "Person"),
    ("Ticket",   "REPORTED_BY", "Person"),
    ("Ticket",   "BLOCKS",      "Release"),
    ("Ticket",   "BLOCKS",      "Ticket"),
    ("Incident", "AFFECTED",    "Service"),
    ("Incident", "ASSIGNED_TO", "Person"),
    ("Decision", "DECIDED_BY",  "Team"),
    ("Decision", "PROPOSED_BY", "Person"),
    ("Decision", "APPROVED_BY", "Person"),
    ("Decision", "AFFECTS",     "Project"),
    ("Document", "AUTHORED_BY", "Person"),
    ("Document", "ABOUT",       "Project"),
    ("Document", "ABOUT",       "Service"),
    ("Document", "DOCUMENTS",   "Decision"),
    ("Document", "DOCUMENTS",   "Incident"),
    # Vector side, linking text to the graph (the "bridge" in the diagram)
    ("Parent",   "PART_OF",     "Document"),
    ("Chunk",    "CHILD_OF",    "Parent"),
    ("Chunk",    "MENTIONS",    "Person"),      # also Project, Service, Team, Tool, ...
)

REL_TYPES: frozenset[str] = frozenset(r for _, r, _ in RELATIONSHIPS)

# --------------------------------------------------------------------------- #
# Index names (referenced by retrieval code)
# --------------------------------------------------------------------------- #
CHUNK_VECTOR_INDEX = "chunk_embedding"   # vector index on (:Chunk).embedding
CHUNK_FULLTEXT_INDEX = "chunk_text"      # full-text (BM25) index on (:Chunk).text
ENTITY_FULLTEXT_INDEX = "entity_names"   # full-text index on names + aliases (entity linking)


def constraint_statements() -> list[str]:
    """One uniqueness constraint per label on `id`. Makes MERGE fast and safe."""
    return [
        f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        for label in ALL_LABELS
    ]


def entity_fulltext_statement() -> str:
    """Full-text index over entity names and aliases, used by the entity linker (Q2)."""
    labels = "|".join(l for l in ENTITY_LABELS if l != "Document")
    return (
        f"CREATE FULLTEXT INDEX {ENTITY_FULLTEXT_INDEX} IF NOT EXISTS "
        f"FOR (n:{labels}) ON EACH [n.name, n.aliases_text]"
    )


def chunk_fulltext_statement() -> str:
    """Full-text (Lucene BM25) index over chunk text, used by hybrid retrieval (Q3B)."""
    return f"CREATE FULLTEXT INDEX {CHUNK_FULLTEXT_INDEX} IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]"


def chunk_vector_statement(dimensions: int) -> str:
    """
    Vector index over chunk embeddings (Neo4j 5.11+).
    Dimensions must match the embedding model, so we detect it at ingest time.
    """
    return (
        f"CREATE VECTOR INDEX {CHUNK_VECTOR_INDEX} IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dimensions)}, "
        f"`vector.similarity_function`: 'cosine'}}}}"
    )


# --------------------------------------------------------------------------- #
# Schema description shown to the LLM
# --------------------------------------------------------------------------- #
SCHEMA_DESCRIPTION = """
Node labels and key properties (every node has id and name):
  Person   {id, name, title, email}
  Team     {id, name}
  Project  {id, name, category ('audit'|'infrastructure'|'data-platform'|'product'), status, start_date, end_date}
  Service  {id, name, tier}
  Tool     {id, name}
  Release  {id, name, target_date}
  Decision {id, name, status, date, tags (list of strings, e.g. 'api-security')}
  Incident {id, name, summary, severity, created}
  Ticket   {id, key, name, summary, status ('Open'|'In Progress'|'In Review'|'Done'), priority, created}
  Document {id, name, doc_type, path}

Relationships:
  (Person)-[:MEMBER_OF]->(Team)
  (Person)-[:WORKED_ON {role, start_date, end_date}]->(Project)
  (Project)-[:OWNED_BY]->(Team)
  (Project)-[:USES]->(Tool), (Service)-[:USES]->(Tool)
  (Team)-[:OWNS]->(Service), (Person)-[:OWNS]->(Service)
  (Service)-[:DEPENDS_ON]->(Service), (Release)-[:DEPENDS_ON]->(Service)
  (Release)-[:PART_OF]->(Project), (Ticket)-[:PART_OF]->(Project)
  (Ticket)-[:ASSIGNED_TO]->(Person), (Ticket)-[:REPORTED_BY]->(Person)
  (Ticket)-[:BLOCKS]->(Release), (Ticket)-[:BLOCKS]->(Ticket)
  (Incident)-[:AFFECTED]->(Service), (Incident)-[:ASSIGNED_TO]->(Person)
  (Decision)-[:DECIDED_BY]->(Team), (Decision)-[:PROPOSED_BY]->(Person)
  (Decision)-[:APPROVED_BY]->(Person), (Decision)-[:AFFECTS]->(Project)
  (Document)-[:AUTHORED_BY]->(Person), (Document)-[:ABOUT]->(Project|Service)
  (Document)-[:DOCUMENTS]->(Decision|Incident)

Dates are ISO strings 'YYYY-MM-DD', so they compare correctly as text.
""".strip()
