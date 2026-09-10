"""
CLI entrypoint for the ingestion package.

Examples:
    python -m app.ingestion
    python -m app.ingestion --topic Technology
    python -m app.ingestion --topic Technology --max-items 10
    python -m app.ingestion --help
"""

import argparse
import json
import sys

from app.ingestion.service import ingest_all_active_sources


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RSS ingestion for WhatsNews topics.",
        epilog=(
            "With no flags, ingests all active topics and all entries per feed "
            "(production behavior). Use --topic and/or --max-items to speed up "
            "local development."
        ),
    )
    parser.add_argument(
        "--topic",
        metavar="NAME",
        help="Ingest only this topic (exact name, e.g. Technology)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        metavar="N",
        dest="max_items",
        help="Process at most N articles per feed after RSS parsing (dev shortcut)",
    )
    args = parser.parse_args()

    if args.max_items is not None and args.max_items < 1:
        parser.error("--max-items must be a positive integer")

    result = ingest_all_active_sources(
        topic=args.topic,
        max_items_per_feed=args.max_items,
    )
    print(json.dumps(result, indent=2))

    if args.topic and result.get("topics_processed", 0) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
