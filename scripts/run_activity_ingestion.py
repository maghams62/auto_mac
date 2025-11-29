#!/usr/bin/env python3
"""
Utility script to run Slack + Git ingestion once.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.ingestion import GitActivityIngestor, SlackActivityIngestor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run activity ingestion jobs (Slack + Git).")
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["slack", "git"],
        help="Limit ingestion to specific sources",
    )
    args = parser.parse_args()

    config = get_config()

    sources = set(args.sources or ["slack", "git"])
    exit_code = 0

    if "slack" in sources:
        slack_ingestor = SlackActivityIngestor(config)
        result = slack_ingestor.ingest()
        slack_ingestor.close()
        print(f"[SLACK] {result}")

    if "git" in sources:
        git_ingestor = GitActivityIngestor(config)
        result = git_ingestor.ingest()
        git_ingestor.close()
        print(f"[GIT] {result}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

