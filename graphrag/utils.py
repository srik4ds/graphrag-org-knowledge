"""
Small helpers shared by several modules.
"""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

log = logging.getLogger("graphrag")


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def setup_logging(level: int = logging.INFO) -> None:
    """One-line, readable log format for the CLI scripts."""
    logging.basicConfig(level=level, format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")


# --------------------------------------------------------------------------- #
# Token counting
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _encoder():
    """
    tiktoken's cl100k encoder, used only to COUNT tokens for chunk sizing.
    Returns None if tiktoken or its encoding file is unavailable; we then fall back
    to an approximation (1 token is about 4 characters of English).
    """
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001  (offline machines, missing package)
        return None


def token_len(text: str) -> int:
    """Approximate number of tokens in text."""
    enc = _encoder()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 4)


def trim_to_tokens(text: str, max_tokens: int) -> str:
    """Cut text so it fits in max_tokens (character-based cut, good enough for context budgets)."""
    if token_len(text) <= max_tokens:
        return text
    ratio = max_tokens / token_len(text)
    return text[: int(len(text) * ratio * 0.97)].rstrip() + " ..."


# --------------------------------------------------------------------------- #
# JSON from LLM output
# --------------------------------------------------------------------------- #
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    """
    Extract the first JSON object from an LLM reply.

    Open models often wrap JSON in ```json fences or add a sentence before it.
    We strip fences, then take the outermost {...} block.
    """
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = _JSON_BLOCK.search(cleaned)
    if not match:
        raise ValueError(f"No JSON object found in LLM output: {text[:200]!r}")
    return json.loads(match.group(0))


# --------------------------------------------------------------------------- #
# Lucene (Neo4j full-text) query escaping
# --------------------------------------------------------------------------- #
_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were", "be",
    "what", "which", "who", "whom", "why", "how", "when", "where", "did", "do", "does", "has", "have",
    "with", "by", "that", "this", "it", "its", "their", "they", "them", "each", "all", "any", "from",
}


def lucene_escape(text: str) -> str:
    """Escape characters that have a meaning in Lucene query syntax."""
    return _LUCENE_SPECIAL.sub(r"\\\1", text)


def to_lucene_keywords(question: str, fuzzy: bool = False) -> str:
    """
    Turn a natural-language question into a Lucene OR-query of its keywords.

    Example: "Who owns ledger-db?" -> "owns OR ledger\\-db"
    fuzzy=True appends ~ so small typos still match ("Trtion~" finds "Triton").
    """
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-\.]*", question)
    terms = []
    for w in words:
        if w.lower() in _STOPWORDS or len(w) < 2:
            continue
        term = lucene_escape(w.strip("."))
        if fuzzy and len(w) >= 5:
            term += "~"
        terms.append(term)
    return " OR ".join(terms) if terms else lucene_escape(question)


# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #
@contextmanager
def timer() -> Iterator[dict]:
    """
    Usage:
        with timer() as t:
            do_work()
        print(t["ms"])
    """
    box: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield box
    finally:
        box["ms"] = round((time.perf_counter() - start) * 1000, 1)


def slugify(text: str) -> str:
    """'Snowpipe Streaming' -> 'snowpipe_streaming' (used to build stable ids)."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
