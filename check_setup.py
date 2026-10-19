"""
Check that credentials and services work before ingesting.

    python check_setup.py

Checks, in order:
    1. .env values are present
    2. Nebius chat model answers
    3. Nebius embedding model returns a vector (and its size)
    4. Neo4j is reachable and supports vector indexes (version 5.11+)
"""

from __future__ import annotations

import re
import sys

from graphrag.config import get_settings


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    s = get_settings()
    failures = 0

    print("1. Environment")
    missing = s.missing_for_llm() + s.missing_for_neo4j()
    if missing:
        _fail(f"missing in .env: {', '.join(missing)}")
        return 1
    _ok(f"LLM={s.llm_model}  EMBEDDINGS={s.embedding_model}  NEO4J={s.neo4j_uri}")

    from graphrag.clients import get_embeddings, get_graph, get_llm

    if s.llm_provider == "offline":
        print("2-3. LLM_PROVIDER=offline: skipping Nebius checks")
    print("2. Nebius chat model")
    try:
        reply = get_llm(s).invoke("Reply with the single word: ready").content
        _ok(f"reply: {reply.strip()[:40]!r}")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        _fail(f"{exc}  (check NEBIUS_API_KEY, NEBIUS_BASE_URL and LLM_MODEL)")

    print("3. Nebius embedding model")
    try:
        dims = len(get_embeddings(s).embed_query("hello"))
        _ok(f"vector size {dims}")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        _fail(f"{exc}  (check EMBEDDING_MODEL is available in your Nebius account)")

    print("4. Neo4j")
    try:
        graph = get_graph(s)
        info = graph.query("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS v, edition")
        version = info[0]["v"]
        _ok(f"{info[0]['name']} {version} ({info[0]['edition']})")
        # Aura reports versions like "5.27-aura"; keep only the leading digits of each part
        major, minor = (int(re.match(r"\d+", x).group()) for x in version.split(".")[:2])
        if (major, minor) < (5, 11) and major < 2025:
            failures += 1
            _fail("vector indexes need Neo4j 5.11 or newer")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        _fail(f"{exc}  (check NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)")

    print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
