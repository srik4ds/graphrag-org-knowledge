"""
Build the knowledge graph and the chunk store (diagram boxes 1A to 6B).

Examples
    python ingest.py --dry-run          # parse + chunk only, no database, no API calls
    python ingest.py --reset            # wipe Neo4j, then load everything
    python ingest.py --skip-vectors     # graph only (no embedding calls)
"""

from __future__ import annotations

import argparse
import json

from graphrag.config import get_settings
from graphrag.ingest.pipeline import prepare, run_ingest
from graphrag.utils import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete all nodes before loading")
    parser.add_argument("--skip-vectors", action="store_true", help="load the graph only")
    parser.add_argument("--dry-run", action="store_true", help="prepare data without touching Neo4j or Nebius")
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()
    if args.dry_run:
        data = prepare(settings)
        print(json.dumps(data.stats, indent=2))
        if data.graph.unresolved:
            print("Unresolved references:", *data.graph.unresolved, sep="\n  ")
        return
    summary = run_ingest(settings, reset=args.reset, skip_vectors=args.skip_vectors)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
