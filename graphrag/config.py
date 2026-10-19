"""
Central configuration.

Every tunable value lives here and is read from environment variables (or a .env
file in the project root). Nothing else in the code base reads os.environ, so this
is the single place to look when you want to change a model, a chunk size or a
threshold.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Project root = folder that contains this package
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env once, at import time. Existing environment variables win.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable, treating empty strings as missing."""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    return str(_env(name, str(default))).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    """All runtime settings. Create with Settings.from_env()."""

    # ---- Provider: "nebius" (any OpenAI-compatible API) or "offline" ----------
    llm_provider: str

    # ---- Nebius (OpenAI-compatible endpoint) ---------------------------------
    nebius_api_key: str | None
    nebius_base_url: str
    llm_model: str                 # used by router, synthesis, grounding
    judge_model: str               # used by the evaluation judge
    embedding_model: str

    # ---- Neo4j ----------------------------------------------------------------
    neo4j_uri: str | None
    neo4j_username: str
    neo4j_password: str | None
    neo4j_database: str

    # ---- Data locations -------------------------------------------------------
    data_dir: Path
    wiki_dir: Path
    issues_dir: Path
    comms_dir: Path
    directory_file: Path
    eval_file: Path
    results_dir: Path

    # ---- Chunking (box 4B) ----------------------------------------------------
    parent_chunk_tokens: int
    child_chunk_tokens: int
    child_chunk_overlap: int

    # ---- Retrieval (boxes Q3A, Q3B) -------------------------------------------
    dense_top_k: int               # children fetched by vector search
    bm25_top_k: int                # children fetched by full-text search
    rrf_k: int                     # the "60" in 1 / (60 + rank)
    final_child_top_k: int         # children kept after RRF (and optional rerank)
    rerank_mode: str               # "none" or "llm"
    enable_text2cypher: bool       # LLM-written Cypher when no template fits

    # ---- Generation and grounding (boxes Q4 to Q6) ----------------------------
    max_context_tokens: int
    grounding_threshold: float     # share of claims that must be supported

    # ---- Misc -----------------------------------------------------------------
    today: str                     # "today" for questions like "last audit"
    embed_batch_size: int = 32
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(_env("DATA_DIR", str(PROJECT_ROOT / "data" / "raw")))
        return cls(
            llm_provider=_env("LLM_PROVIDER", "nebius").lower(),
            nebius_api_key=_env("NEBIUS_API_KEY"),
            nebius_base_url=_env("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
            llm_model=_env("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
            judge_model=_env("JUDGE_MODEL", _env("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")),
            embedding_model=_env("EMBEDDING_MODEL", "BAAI/bge-en-icl"),
            neo4j_uri=_env("NEO4J_URI"),
            neo4j_username=_env("NEO4J_USERNAME", "neo4j"),
            neo4j_password=_env("NEO4J_PASSWORD"),
            neo4j_database=_env("NEO4J_DATABASE", "neo4j"),
            data_dir=data_dir,
            wiki_dir=data_dir / "wiki",
            issues_dir=data_dir / "issues",
            comms_dir=data_dir / "comms",
            directory_file=data_dir / "directory_map.json",
            eval_file=Path(_env("EVAL_FILE", str(PROJECT_ROOT / "eval" / "queries.json"))),
            results_dir=Path(_env("RESULTS_DIR", str(PROJECT_ROOT / "results"))),
            parent_chunk_tokens=_env_int("PARENT_CHUNK_TOKENS", 1024),
            child_chunk_tokens=_env_int("CHILD_CHUNK_TOKENS", 256),
            child_chunk_overlap=_env_int("CHILD_CHUNK_OVERLAP", 32),
            dense_top_k=_env_int("DENSE_TOP_K", 20),
            bm25_top_k=_env_int("BM25_TOP_K", 20),
            rrf_k=_env_int("RRF_K", 60),
            final_child_top_k=_env_int("FINAL_CHILD_TOP_K", 5),
            rerank_mode=_env("RERANK_MODE", "none").lower(),
            enable_text2cypher=_env_bool("ENABLE_TEXT2CYPHER", True) and _env("LLM_PROVIDER", "nebius").lower() != "offline",
            max_context_tokens=_env_int("MAX_CONTEXT_TOKENS", 6000),
            grounding_threshold=_env_float("GROUNDING_THRESHOLD", 0.8),
            today=_env("TODAY", date.today().isoformat()),
            embed_batch_size=_env_int("EMBED_BATCH_SIZE", 32),
        )

    # ---- Validation helpers used by check_setup.py ---------------------------
    def missing_for_llm(self) -> list[str]:
        if self.llm_provider == "offline":
            return []
        return [n for n, v in [("NEBIUS_API_KEY", self.nebius_api_key)] if not v]

    def missing_for_neo4j(self) -> list[str]:
        return [n for n, v in [("NEO4J_URI", self.neo4j_uri), ("NEO4J_PASSWORD", self.neo4j_password)] if not v]


def get_settings() -> Settings:
    """Convenience accessor used across the code base."""
    return Settings.from_env()
