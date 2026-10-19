"""
graphrag: GraphRAG for Organizational Knowledge.

Package layout (mirrors the data flow diagram):

    graphrag/config.py        Settings loaded from .env
    graphrag/clients.py       Factories for the LLM, embeddings and Neo4j connection
    graphrag/utils.py         Small shared helpers (token counting, JSON parsing, timers)
    graphrag/schema.py        Graph labels, relationship types, constraints and indexes

    graphrag/ingest/          BUILD TIME   (boxes 1A to 6B)
    graphrag/retrieval/       QUERY TIME   retrieval building blocks (Q3A, Q3B)
    graphrag/agent/           QUERY TIME   LangGraph orchestration (Q2 to Q7)
    graphrag/evaluation/      EVALUATION   (E1 to E4)
"""

__version__ = "1.0.0"
