#!/usr/bin/env python
"""
Build vector indexes from synthetic datasets (Slack first, Git later).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.vector.indexers.slack_indexer import SlackVectorIndexer
from src.vector.indexers.git_indexer import GitVectorIndexer
from src.vector.indexers.doc_indexer import DocVectorIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_vector_index")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build synthetic vector indexes.")
    parser.add_argument(
        "--domain",
        choices=["slack", "git", "docs", "all"],
        default="slack",
        help="Which domain(s) to index.",
    )
    parser.add_argument(
        "--slack-path",
        type=Path,
        default=Path("data/synthetic_slack/slack_events.json"),
        help="Path to the synthetic Slack ledger.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/vector_index/slack_index.json"),
        help="Destination for the local vector store.",
    )
    parser.add_argument(
        "--git-events-path",
        type=Path,
        default=Path("data/synthetic_git/git_events.json"),
        help="Path to synthetic git events JSON.",
    )
    parser.add_argument(
        "--git-prs-path",
        type=Path,
        default=Path("data/synthetic_git/git_prs.json"),
        help="Path to synthetic git PRs JSON.",
    )
    parser.add_argument(
        "--git-output",
        type=Path,
        default=Path("data/vector_index/git_index.json"),
        help="Destination for git vector store.",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("data/synthetic_git"),
        help="Root directory containing synthetic doc files.",
    )
    parser.add_argument(
        "--docs-output",
        type=Path,
        default=Path("data/vector_index/doc_index.json"),
        help="Destination for doc vector store.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ConfigManager().get_config()

    results = {}

    def _run_slack():
        indexer = SlackVectorIndexer(
            config,
            data_path=args.slack_path,
            output_path=args.output,
        )
        results["slack"] = indexer.build()

    def _run_git():
        indexer = GitVectorIndexer(
            config,
            events_path=args.git_events_path,
            prs_path=args.git_prs_path,
            output_path=args.git_output,
        )
        results["git"] = indexer.build()

    def _run_docs():
        indexer = DocVectorIndexer(
            config,
            docs_root=args.docs_root,
            output_path=args.docs_output,
        )
        results["docs"] = indexer.build()

    if args.domain == "slack":
        _run_slack()
    elif args.domain == "git":
        _run_git()
    elif args.domain == "docs":
        _run_docs()
    elif args.domain == "all":
        _run_slack()
        _run_git()
        _run_docs()
    else:
        raise NotImplementedError(f"Unsupported domain: {args.domain}")

    for domain, stats in results.items():
        logger.info("[VECTOR INDEX] %s -> %s", domain, stats)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

