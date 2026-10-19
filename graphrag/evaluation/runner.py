"""
E1 to E4: run the 10 questions through both modes and write a comparison report.

Outputs (version-numbered so earlier runs are never overwritten):
    results/eval_results_vN.csv   one row per (question, mode)
    results/eval_report_vN.md     summary table, per-question winners, full answers
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from graphrag.agent.builder import ask, build_deps, build_graph
from graphrag.clients import get_llm
from graphrag.config import Settings
from graphrag.evaluation.judges import fact_recall, llm_judge
from graphrag.utils import log

MODES = ("graphrag", "vector")


@dataclass
class EvalRow:
    qid: str
    mode: str
    question: str
    expected_winner: str
    status: str
    answer: str
    latency_ms: float
    faithfulness: float | None
    correctness: float
    relevance: float
    fact_recall: float
    graph_strategy: str
    entities: str
    judge_note: str


def _next_version(folder: Path, stem: str, suffix: str) -> Path:
    """results/eval_report_v3.md if v1 and v2 exist."""
    folder.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in folder.glob(f"{stem}_v*{suffix}") if (m := re.search(r"_v(\d+)", p.stem))]
    return folder / f"{stem}_v{max(nums, default=0) + 1}{suffix}"


def run_evaluation(settings: Settings, only: list[str] | None = None) -> tuple[Path, Path]:
    queries = json.loads(settings.eval_file.read_text())["queries"]
    if only:
        queries = [q for q in queries if q["id"] in only]

    agent = build_graph(build_deps(settings))
    judge = get_llm(settings, model=settings.judge_model)
    rows: list[EvalRow] = []

    for q in queries:
        for mode in MODES:
            log.info("[%s] %s mode ...", q["id"], mode)
            state = ask(agent, q["question"], mode=mode)
            answer = state.get("answer", "")
            refused = state.get("status") != "answered"
            g = state.get("grounding", {})
            verdict = {"correctness": 0.0, "relevance": 0.0, "explanation": "refused"} if refused \
                else llm_judge(judge, q["question"], q["gold_answer"], answer)
            rows.append(EvalRow(
                qid=q["id"], mode=mode, question=q["question"], expected_winner=q.get("expected_winner", ""),
                status=state.get("status", "error"), answer=answer, latency_ms=state.get("wall_ms", 0.0),
                faithfulness=None if refused else g.get("ratio"),
                correctness=verdict["correctness"], relevance=verdict["relevance"],
                fact_recall=0.0 if refused else fact_recall(answer, q.get("must_include", []), q.get("must_exclude")),
                graph_strategy=state.get("graph_strategy", "-"),
                entities=", ".join(e["name"] for e in state.get("entities", [])),
                judge_note=verdict["explanation"],
            ))

    csv_path = _next_version(settings.results_dir, "eval_results", ".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)

    md_path = _next_version(settings.results_dir, "eval_report", ".md")
    md_path.write_text(render_report(rows, queries), encoding="utf-8")
    log.info("Wrote %s and %s", csv_path, md_path)
    return csv_path, md_path


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _mean(values) -> float:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else 0.0


def _p95(values) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    return round(values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))], 1)


def _winner(g: EvalRow, v: EvalRow) -> str:
    if (g.correctness, g.fact_recall) > (v.correctness, v.fact_recall):
        return "GraphRAG"
    if (g.correctness, g.fact_recall) < (v.correctness, v.fact_recall):
        return "Vector"
    return "Tie"


def render_report(rows: list[EvalRow], queries: list[dict]) -> str:
    by = {(r.qid, r.mode): r for r in rows}
    out = ["# GraphRAG vs Vector RAG: evaluation report", ""]

    # ---- summary ------------------------------------------------------------
    out += ["## Summary", "",
            "| # | Metric | GraphRAG | Vector-only |", "|---|---|---|---|"]
    metrics = [
        ("Correctness (avg, 0-1)", lambda rs: _mean(r.correctness for r in rs)),
        ("Relevance (avg, 0-1)", lambda rs: _mean(r.relevance for r in rs)),
        ("Faithfulness (avg of answered)", lambda rs: _mean(r.faithfulness for r in rs)),
        ("Fact recall (avg)", lambda rs: _mean(r.fact_recall for r in rs)),
        ("Refusals", lambda rs: sum(1 for r in rs if r.status != "answered")),
        ("Latency p50 (ms)", lambda rs: round(statistics.median([r.latency_ms for r in rs]), 1)),
        ("Latency p95 (ms)", lambda rs: _p95([r.latency_ms for r in rs])),
    ]
    for i, (name, fn) in enumerate(metrics, start=1):
        g = [r for r in rows if r.mode == "graphrag"]
        v = [r for r in rows if r.mode == "vector"]
        out.append(f"| {i} | {name} | {fn(g)} | {fn(v)} |")

    # ---- per question ---------------------------------------------------------
    out += ["", "## Per-question comparison", "",
            "| # | Id | Question | Expected | GraphRAG correctness | Vector correctness | Winner |",
            "|---|---|---|---|---|---|---|"]
    for i, q in enumerate(queries, start=1):
        g, v = by.get((q["id"], "graphrag")), by.get((q["id"], "vector"))
        if not g or not v:
            continue
        out.append(f"| {i} | {q['id']} | {q['question']} | {q.get('expected_winner', '')} | "
                   f"{g.correctness} | {v.correctness} | {_winner(g, v)} |")

    # ---- details ----------------------------------------------------------------
    out += ["", "## Answers", ""]
    for q in queries:
        out += [f"### {q['id']}: {q['question']}", "", f"**Gold:** {q['gold_answer']}", ""]
        for mode in MODES:
            r = by.get((q["id"], mode))
            if r:
                out += [f"**{mode}** ({r.status}, {r.latency_ms} ms, correctness {r.correctness}, "
                        f"recall {r.fact_recall}, strategy {r.graph_strategy}):", "", r.answer, "",
                        f"_Judge: {r.judge_note}_", ""]
    return "\n".join(out)
