"""
Scoring functions for E3.

Four metrics per answer:
    faithfulness   share of claims supported by the retrieved context
                   (taken from the pipeline's own grounding check, Q6)
    correctness    LLM judge: 0, 0.5 or 1 versus the gold answer
    relevance      LLM judge: 0, 0.5 or 1, does the answer address the question
    fact_recall    deterministic: share of must_include strings found in the answer
A refusal scores 0 on correctness, relevance and fact recall.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from graphrag.utils import log, parse_json_object

JUDGE_PROMPT = """You grade answers from a question-answering system.

Question: {question}
Gold answer: {gold}
System answer: {answer}

Score two things, each 0, 0.5 or 1:
- correctness: 1 if the system answer states the key facts of the gold answer and nothing that contradicts it;
  0.5 if partly correct or incomplete; 0 if wrong, missing or a refusal.
- relevance: 1 if the answer directly addresses the question; 0.5 if partly; 0 if not.

Return ONLY JSON: {{"correctness": <0|0.5|1>, "relevance": <0|0.5|1>, "explanation": "<one sentence>"}}
"""


def fact_recall(answer: str, must_include: list[str], must_exclude: list[str] | None = None) -> float:
    """Share of required strings present (case-insensitive). Any forbidden string halves the score."""
    if not must_include:
        return 1.0
    text = answer.lower()
    score = sum(1 for s in must_include if s.lower() in text) / len(must_include)
    if any(s.lower() in text for s in (must_exclude or [])):
        score *= 0.5
    return round(score, 3)


def llm_judge(llm: BaseChatModel, question: str, gold: str, answer: str) -> dict:
    try:
        result = parse_json_object(llm.invoke(JUDGE_PROMPT.format(question=question, gold=gold, answer=answer)).content)
        return {"correctness": float(result.get("correctness", 0)), "relevance": float(result.get("relevance", 0)),
                "explanation": result.get("explanation", "")}
    except Exception as exc:  # noqa: BLE001
        log.warning("Judge failed: %s", exc)
        return {"correctness": 0.0, "relevance": 0.0, "explanation": f"judge error: {exc}"}
