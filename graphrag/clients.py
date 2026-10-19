"""
Factories for external clients.

Keeping client construction in one module means the rest of the code only asks for
"an LLM", "embeddings" or "the graph" and never deals with keys or URLs.

Nebius exposes an OpenAI-compatible API, so the standard LangChain OpenAI classes
work once base_url points at Nebius.
"""

from __future__ import annotations

from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from graphrag.config import Settings


def get_llm(settings: Settings, model: str | None = None, temperature: float = 0.0) -> ChatOpenAI:
    """Chat model on Nebius. temperature=0 keeps routing and judging deterministic."""
    if settings.llm_provider == "offline":          # LLM_PROVIDER=offline: rule-based stand-in
        from graphrag.offline import OfflineLLM
        return OfflineLLM()
    return ChatOpenAI(
        model=model or settings.llm_model,
        base_url=settings.nebius_base_url,
        api_key=settings.nebius_api_key,
        temperature=temperature,
        max_retries=3,
        timeout=90,
    )


def get_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """
    Embedding model on Nebius.

    check_embedding_ctx_length=False is important: by default LangChain tokenizes the
    text with OpenAI's tokenizer and sends token ids, which non-OpenAI providers do
    not accept. With False, plain strings are sent.
    """
    if settings.llm_provider == "offline":          # LLM_PROVIDER=offline: local hashing embeddings
        from graphrag.offline import HashingEmbeddings
        return HashingEmbeddings()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.nebius_base_url,
        api_key=settings.nebius_api_key,
        check_embedding_ctx_length=False,
        chunk_size=settings.embed_batch_size,   # texts per API call
        max_retries=3,
    )


def get_graph(settings: Settings) -> Neo4jGraph:
    """
    Connection to Neo4j AuraDB (or a local Neo4j 5.11+).

    refresh_schema=False skips the APOC schema scan at connect time; we keep our own
    schema description in graphrag/schema.py.
    """
    return Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
        refresh_schema=False,
    )
