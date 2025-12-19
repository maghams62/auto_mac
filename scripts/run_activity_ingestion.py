#!/usr/bin/env python3
"""
Utility script to run Slack + Git ingestion once.

Example cron (runs every 10 minutes):
*/10 * * * * /usr/bin/env bash -lc 'cd /opt/oqoqo && source venv/bin/activate && python scripts/run_activity_ingestion.py'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Set

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.ingestion import DocIssueIngestor, GitActivityIngestor, SlackActivityIngestor
from src.settings.runtime_mode import build_runtime_flags


def main() -> int:
    parser = argparse.ArgumentParser(description="Run activity ingestion jobs (Slack, Git, Doc issues).")
    parser.add_argument(
        "--sources",
        nargs="*",
        help="Limit ingestion to specific sources (comma-separated or repeated: slack git doc_issues)",
    )
    parser.add_argument(
        "--force-live",
        action="store_true",
        help="Bypass runtime-mode safety checks and hit live APIs even in dev/demo.",
    )
    parser.add_argument(
        "--fixture-repo-id",
        default="fixtures:activity",
        help="Repo identifier used when ingesting git fixtures (default: %(default)s).",
    )
    args = parser.parse_args()

    config = get_config()
    runtime_flags = build_runtime_flags(config)

    def allowed_sources(raw: Iterable[str] | None) -> Set[str]:
        valid = {"slack", "git", "doc_issues"}
        if not raw:
            return set(valid)
        selected: Set[str] = set()
        for token in raw:
            for part in token.split(","):
                name = part.strip().lower()
                if not name:
                    continue
                if name not in valid:
                    parser.error(f"Unknown source '{name}'. Allowed values: {', '.join(sorted(valid))}")
                selected.add(name)
        return selected or set(valid)

    sources = allowed_sources(args.sources)
    exit_code = 0

    activity_cfg = config.get("activity_ingest") or {}
    slack_cfg = activity_cfg.get("slack") or {}
    git_cfg = activity_cfg.get("git") or {}
    doc_cfg = activity_cfg.get("doc_issues") or {}

    mode_summary = (
        f"[MODE] CEREBROS_MODE={runtime_flags.mode.value} "
        f"(force_live={args.force_live}, fixtures={'on' if runtime_flags.enable_fixtures else 'off'})"
    )
    print(mode_summary)

    if "slack" in sources:
        if not slack_cfg.get("enabled", False):
            print("[SLACK] Skipped (activity_ingest.slack.enabled is false)")
        else:
            slack_ingestor = SlackActivityIngestor(config)
            result = _run_slack_ingest(slack_ingestor, slack_cfg, runtime_flags, args.force_live)
            slack_ingestor.close()
            print(f"[SLACK] {result}")

    if "git" in sources:
        if not git_cfg.get("enabled", False):
            print("[GIT] Skipped (activity_ingest.git.enabled is false)")
        else:
            git_ingestor = GitActivityIngestor(config)
            result = _run_git_ingest(
                git_ingestor,
                git_cfg,
                runtime_flags,
                args.force_live,
                repo_identifier=args.fixture_repo_id,
            )
            git_ingestor.close()
            print(f"[GIT] {result}")

    if "doc_issues" in sources:
        if not doc_cfg.get("enabled", False):
            print("[DOC ISSUES] Skipped (activity_ingest.doc_issues.enabled is false)")
        else:
            doc_ingestor = DocIssueIngestor(config)
            result = doc_ingestor.ingest()
            doc_ingestor.close()
            print(f"[DOC ISSUES] {result}")

    return exit_code


def _run_slack_ingest(
    ingestor: SlackActivityIngestor,
    slack_cfg: Dict[str, Any],
    runtime_flags,
    force_live: bool,
) -> Dict[str, Any]:
    if runtime_flags.enable_live_slack or force_live:
        return ingestor.ingest()

    if not runtime_flags.enable_fixtures:
        print("[SLACK] Live ingestion disabled in this mode and fixtures are unavailable; skipping.")
        return {"ingested": 0}

    fixture_path = slack_cfg.get("fixture_path")
    if not fixture_path:
        print("[SLACK] No fixture_path configured; skipping fixture ingestion.")
        return {"ingested": 0}

    payload = _load_fixture_payload(fixture_path)
    if isinstance(payload, list):
        payload = {"messages": payload}
    if not isinstance(payload, dict):
        print(f"[SLACK] Fixture file {fixture_path} must be a dict or list; skipping.")
        return {"ingested": 0}
    messages = payload.get("messages") or []
    if not messages:
        print(f"[SLACK] Fixture file {fixture_path} contains no 'messages'; skipping.")
        return {"ingested": 0}
    print(f"[SLACK] Ingesting {len(messages)} fixture messages from {fixture_path}")
    return ingestor.ingest_fixture_messages(payload)


def _run_git_ingest(
    ingestor: GitActivityIngestor,
    git_cfg: Dict[str, Any],
    runtime_flags,
    force_live: bool,
    *,
    repo_identifier: str,
) -> Dict[str, Any]:
    if runtime_flags.enable_live_git or force_live:
        return ingestor.ingest()

    if not runtime_flags.enable_fixtures:
        print("[GIT] Live ingestion disabled in this mode and fixtures are unavailable; skipping.")
        return {"prs": 0, "commits": 0, "issues": 0}

    fixture_path = git_cfg.get("fixture_path")
    if not fixture_path:
        print("[GIT] No fixture_path configured; skipping fixture ingestion.")
        return {"prs": 0, "commits": 0, "issues": 0}

    payload = _load_fixture_payload(fixture_path)
    if not isinstance(payload, dict):
        print(f"[GIT] Fixture file {fixture_path} must be a dict; skipping.")
        return {"prs": 0, "commits": 0, "issues": 0}

    total_items = sum(len(payload.get(key) or []) for key in ("pull_requests", "commits", "issues"))
    if total_items == 0:
        print(f"[GIT] Fixture file {fixture_path} has no pull_requests/commits/issues; skipping.")
        return {"prs": 0, "commits": 0, "issues": 0}

    print(f"[GIT] Ingesting fixture data ({total_items} items) from {fixture_path}")
    return ingestor.ingest_fixtures(payload, repo_identifier=repo_identifier)


def _load_fixture_payload(path_str: str) -> Dict[str, Any] | list[Any] | None:
    path = Path(path_str)
    if not path.exists():
        print(f"[FIXTURE] File not found: {path}")
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[FIXTURE] Failed to read {path}: {exc}")
        return None

    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text) or {}
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        print(f"[FIXTURE] Failed to parse {path}: {exc}")
        return None


if __name__ == "__main__":
    raise SystemExit(main())

