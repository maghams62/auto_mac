#!/usr/bin/env python3
"""
Seed synthetic git/slack activity from fixture files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.ingestion import GitActivityIngestor, SlackActivityIngestor


def load_fixture(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic activity fixtures.")
    parser.add_argument("--git-fixture", type=Path, help="Path to git activity fixture YAML")
    parser.add_argument("--slack-fixture", type=Path, help="Path to slack activity fixture YAML")
    parser.add_argument("--repo-id", type=str, default="fixtures:activity", help="Repo identifier for git fixtures")
    args = parser.parse_args()

    if not args.git_fixture and not args.slack_fixture:
        parser.error("Provide --git-fixture and/or --slack-fixture")

    config = get_config()

    if args.git_fixture:
        git_data = load_fixture(args.git_fixture)
        git_ingestor = GitActivityIngestor(config)
        result = git_ingestor.ingest_fixtures(git_data, repo_identifier=args.repo_id)
        git_ingestor.close()
        print(f"[GIT FIXTURE] {result}")

    if args.slack_fixture:
        slack_data = load_fixture(args.slack_fixture)
        slack_ingestor = SlackActivityIngestor(config)
        result = slack_ingestor.ingest_fixture_messages(slack_data)
        slack_ingestor.close()
        print(f"[SLACK FIXTURE] {result}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

