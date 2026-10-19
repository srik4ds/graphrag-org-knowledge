"""
Ask one question from the command line and print the answer with its evidence.

Examples
    python ask.py "Who owns ledger-db?"
    python ask.py "Who owns ledger-db?" --mode vector
    python ask.py "Who owns ledger-db?" --debug      # also print context, Cypher and timings
"""

from __future__ import annotations

import argparse
import json

from graphrag.agent.builder import ask, build_agent, total_latency_ms
from graphrag.utils import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["graphrag", "vector"], default="graphrag")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    setup_logging()
    state = ask(build_agent(), args.question, mode=args.mode)

    print("\n" + "=" * 80)
    print(f"[{state.get('status')}] {state.get('answer')}")
    print("=" * 80)
    print(f"Entities : {[e['name'] for e in state.get('entities', [])]}")
    print(f"Template : {state.get('route', {}).get('template')}  |  graph strategy: {state.get('graph_strategy', '-')}")
    print(f"Grounding: {state.get('grounding', {}).get('supported')}/{state.get('grounding', {}).get('total')} claims supported")
    print(f"Latency  : {state.get('wall_ms')} ms wall, {total_latency_ms(state)} ms by node")

    if args.debug:
        print("\n--- CONTEXT ---\n" + state.get("context", ""))
        for q in state.get("graph_queries", []):
            print("\n--- CYPHER ---\n" + q["cypher"] + f"\nparams={q['params']} rows={q['row_count']}")
        print("\n--- TIMINGS ---\n" + json.dumps(state.get("timings", {}), indent=2))
        print("\n--- VECTOR DEBUG ---\n" + json.dumps(state.get("vector_debug", {}), indent=2, default=str))


if __name__ == "__main__":
    main()
