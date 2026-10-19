"""
QUERY TIME retrieval building blocks.

    entity_linker.py      Q2  map phrases from the question to graph node ids
    cypher_templates.py   Q3A parameterized Cypher for common multi-hop questions
    graph_retriever.py    Q3A run a template (or the Text2Cypher fallback) -> graph facts
    text2cypher.py        Q3A fallback: LLM writes read-only Cypher
    rrf.py                Q3B Reciprocal Rank Fusion
    hybrid_retriever.py   Q3B dense + BM25 + RRF (+ optional rerank) -> parent passages
"""
