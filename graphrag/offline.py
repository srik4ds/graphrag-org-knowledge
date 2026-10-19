"""
OFFLINE MODE: run the whole pipeline without any LLM or embedding API.

Enable with LLM_PROVIDER=offline in .env. Useful when no API credits are available.

    HashingEmbeddings   deterministic bag-of-words vectors (no network). Similar wording
                        gives similar vectors, so dense search still works, just less
                        semantically than a real embedding model.
    OfflineLLM          rule-based stand-in that answers the same prompts the real LLM gets:
                          router prompt     -> keyword rules pick template + mentions
                          synthesis prompt  -> extractive answer: quotes graph facts and
                                               passage sentences, each with its [G#]/[V#] tag
                          grounding prompt  -> every quoted claim is supported by construction
                          judge prompt      -> word-overlap score against the gold answer

The graph side (Neo4j, Cypher templates, entity linking, RRF) is exactly the same as in
the real mode, so GraphRAG vs vector comparisons remain meaningful.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from types import SimpleNamespace

from langchain_core.embeddings import Embeddings

_WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were", "be", "what",
         "which", "who", "why", "how", "did", "do", "does", "has", "have", "with", "by", "that", "this", "it",
         "its", "their", "they", "each", "all", "from", "as", "at", "our", "we"}


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
class HashingEmbeddings(Embeddings):
    """Unigrams + bigrams hashed into a fixed-size, L2-normalised vector."""

    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        toks = _tokens(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            vec[h % self.dimensions] += 1.0 if (h >> 64) % 2 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


# --------------------------------------------------------------------------- #
# Rule-based LLM
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _registry():
    """Entity names from the raw data (offline, no database)."""
    from graphrag.config import get_settings
    from graphrag.ingest.pipeline import prepare
    return prepare(get_settings()).registry


def _between(prompt: str, start: str, end: str | None = None) -> str:
    part = prompt.split(start, 1)[-1]
    return part.split(end, 1)[0].strip() if end and end in part else part.strip()


class OfflineLLM:
    """Same .invoke(prompt) -> object with .content interface as a LangChain chat model."""

    def invoke(self, prompt: str) -> SimpleNamespace:
        if "query router" in prompt:
            reply = self._route(prompt.rsplit("Question:", 1)[-1].strip())
        elif "strict fact-checker" in prompt:
            reply = self._ground(_between(prompt, "ANSWER:"))
        elif "You grade answers" in prompt:
            reply = self._judge(_between(prompt, "Gold answer:", "System answer:"), _between(prompt, "System answer:", "Score two"))
        elif "Order the candidate passages" in prompt:
            reply = json.dumps({"order": []})
        elif "Cypher" in prompt and "read-only Cypher query" in prompt:
            reply = "MATCH (n) RETURN n.name LIMIT 0"
        else:
            reply = self._synthesize(_between(prompt, "Question:", "Context:"), _between(prompt, "Context:", "Answer:"))
        return SimpleNamespace(content=reply)

    # ---- router ---------------------------------------------------------------
    @staticmethod
    def _route(q: str) -> str:
        ql = q.lower()
        reg = _registry()
        found = reg.find_mentions(q)
        mentions = [{"text": reg.name_of(i), "label": l, "category": None, "temporal": None} for l, i in found]

        def first(label):
            return [m for m in mentions if m["label"] == label]

        template, anchor = "none", []
        if "audit" in ql and any(w in ql for w in ("last", "latest", "most recent")):
            anchor = [{"text": "last audit", "label": "Project", "category": "audit", "temporal": "latest"}]
            template = "project_people_next_projects"
        elif any(w in ql for w in ("incident", "outage", "failed")) and any(w in ql for w in ("last", "latest", "most recent", "recent")) and "decision" in ql:
            anchor = [{"text": "latest incident", "label": "Incident", "category": None, "temporal": "latest"}]
            template = "incident_owner_decisions"
        elif "leave" in ql and first("Person"):
            anchor, template = first("Person")[:1], "person_departure_impact"
        elif ("block" in ql) and first("Release"):
            anchor, template = first("Release")[:1], "release_blockers"
        elif "decision" in ql or "approved" in ql:
            # pick the decision whose name shares most words with the question
            qt = set(_tokens(q))
            best = max(reg.records("Decision"), key=lambda r: len(qt & set(_tokens(r.name + " " + " ".join(r.aliases)))), default=None)
            if best and len(qt & set(_tokens(best.name + " " + " ".join(best.aliases)))) >= 2:
                anchor, template = [{"text": best.name, "label": "Decision", "category": None, "temporal": None}], "decision_details"
        elif "tool" in ql and first("Person"):
            anchor, template = first("Person")[:1], "person_projects_tools"
        elif "open ticket" in ql and first("Project"):
            anchor, template = first("Project")[:1], "project_open_ticket_load"
        elif first("Service") and any(w in ql for w in ("own", "depend")):
            anchor, template = first("Service")[:1], "service_overview"

        # Prose questions ("why", "root cause", "process") are answered from text: no graph anchor
        if template == "none" and re.match(r"\s*(why|how|what is the|what was the)", ql):
            mentions = []
        rest = [m for m in mentions if m not in anchor]
        return json.dumps({"mentions": anchor + rest, "template": template, "reason": "offline keyword router"})

    # ---- synthesis (extractive) ---------------------------------------------
    @staticmethod
    def _synthesize(question: str, context: str) -> str:
        qt = set(_tokens(question))
        facts = re.findall(r"^\[(G\d+)\] (.+)$", context, re.M)
        lines = [f"{text.rstrip('.')}. [{tag}]" for tag, text in facts[:8]]
        # Passages: pick the sentences that overlap most with the question
        for tag, body in re.findall(r"^\[(V\d+)\] \(source:[^\n]*\)\n(.*?)(?=^\[V\d+\]|\Z)", context, re.M | re.S):
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", body) if len(s.strip()) > 25]
            scored = sorted(sentences, key=lambda s: -len(qt & set(_tokens(s))))
            # keep the 3 best sentences per passage (at least one shared word with the question)
            for s in [s for s in scored if qt & set(_tokens(s))][:3]:
                lines.append(f"{s.rstrip('.')}. [{tag}]")
            if len(lines) >= 12:
                break
        return "\n".join(f"{i}. {l}" for i, l in enumerate(lines, 1)) if lines else "INSUFFICIENT_CONTEXT"

    # ---- grounding / judge ------------------------------------------------------
    @staticmethod
    def _ground(answer: str) -> str:
        claims = [{"claim": l, "citations": re.findall(r"\[([GV]\d+)\]", l), "supported": bool(re.search(r"\[[GV]\d+\]", l)),
                   "note": "extractive"} for l in answer.splitlines() if l.strip()]
        return json.dumps({"claims": claims})

    @staticmethod
    def _judge(gold: str, answer: str) -> str:
        g, a = set(_tokens(gold)), set(_tokens(answer))
        overlap = len(g & a) / len(g) if g else 0.0
        score = 1.0 if overlap >= 0.6 else 0.5 if overlap >= 0.3 else 0.0
        return json.dumps({"correctness": score, "relevance": 1.0 if overlap >= 0.3 else 0.5 if a else 0.0,
                           "explanation": f"offline word overlap {overlap:.2f}"})
