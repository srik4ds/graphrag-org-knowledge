"""
Run the 10-question evaluation in both modes (diagram boxes E1 to E4).

Examples
    python evaluate.py                 # all questions
    python evaluate.py --only Q01 Q07  # a subset while iterating
"""

from __future__ import annotations

import argparse

from graphrag.config import get_settings
from graphrag.evaluation.runner import run_evaluation
from graphrag.utils import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="question ids to run, e.g. Q01 Q05")
    args = parser.parse_args()

    setup_logging()
    csv_path, md_path = run_evaluation(get_settings(), only=args.only)
    print(f"Results: {csv_path}\nReport : {md_path}")


if __name__ == "__main__":
    main()
