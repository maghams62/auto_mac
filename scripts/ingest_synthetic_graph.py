#!/usr/bin/env python
"""
Run the synthetic Neo4j ingester (services/components/APIs/docs/git/slack).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.graph.synthetic_ingester import SyntheticGraphIngester

logging.basicConfig(level=logging.INFO)


def main() -> None:
    config = ConfigManager().get_config()
    ingester = SyntheticGraphIngester(config)
    summary = ingester.ingest()
    print(json.dumps(summary, indent=2))
    logging.info(
        "[GRAPH INGEST] Services=%s Components=%s APIs=%s Docs=%s GitEvents=%s SlackEvents=%s",
        summary.get("services"),
        summary.get("components"),
        summary.get("apis"),
        summary.get("docs"),
        summary.get("git_events"),
        summary.get("slack_events"),
    )


if __name__ == "__main__":
    main()

