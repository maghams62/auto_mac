#!/usr/bin/env python3
"""
Lightweight CLI for common Cerebros workflows.

Usage examples:
    python scripts/cerebros.py ingest slack
    python scripts/cerebros.py ingest git --with-impact
    CEREBROS_MODE=live python scripts/cerebros.py ingest all --force-live
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config_manager import get_config  # noqa: E402


def _run(cmd: List[str]) -> None:
    pretty = " ".join(cmd)
    print(f"\n$ {pretty}")
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _resolve_sources(target: str) -> List[str]:
    target = target.lower()
    if target == "all":
        return ["slack", "git", "doc_issues"]
    if target in {"doc", "doc_issues", "docs"}:
        return ["doc_issues"]
    if target in {"slack", "git"}:
        return [target]
    raise SystemExit(f"Unknown ingest target '{target}'. Use slack, git, doc, or all.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebros helper CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Run activity ingestion (Slack/Git/doc issues).")
    ingest.add_argument(
        "target",
        nargs="?",
        default="all",
        help="Which pipeline to run (slack | git | doc | all). Defaults to all.",
    )
    ingest.add_argument(
        "--force-live",
        action="store_true",
        help="Bypass runtime-mode guardrails and hit live APIs even in dev/demo.",
    )
    ingest.add_argument(
        "--fixture-repo-id",
        default="fixtures:activity",
        help="Repo identifier used when ingesting git fixtures (default: %(default)s).",
    )
    ingest.add_argument(
        "--with-impact",
        action="store_true",
        help="After git/all ingest, run scripts/impact_auto_ingest.py to refresh doc issues.",
    )
    ingest.add_argument(
        "--impact-limit",
        type=int,
        default=20,
        help="Max commits per repo for impact auto-ingest (default: %(default)s).",
    )
    ingest.add_argument(
        "--impact-allow-synthetic",
        action="store_true",
        help="Pass --allow-synthetic to impact_auto_ingest.py (only needed when running in demo mode).",
    )

    status = subparsers.add_parser("status", help="Inspect Cerebros subsystems.")
    status.add_argument(
        "target",
        choices=["activity-graph"],
        help="Which subsystem to inspect (currently only activity-graph).",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        sources = _resolve_sources(args.target)
        cmd = [
            sys.executable,
            "scripts/run_activity_ingestion.py",
            "--sources",
            *sources,
            "--fixture-repo-id",
            args.fixture_repo_id,
        ]
        if args.force_live:
            cmd.append("--force-live")
        _run(cmd)

        if args.with_impact:
            if "git" not in sources and args.target != "all":
                print("[IMPACT] Skipped (impact refresh requires git data).")
            else:
                impact_cmd = [
                    sys.executable,
                    "scripts/impact_auto_ingest.py",
                    "--limit",
                    str(max(1, args.impact_limit)),
                ]
                if args.impact_allow_synthetic:
                    impact_cmd.append("--allow-synthetic")
                _run(impact_cmd)
        return

    if args.command == "status":
        if args.target == "activity-graph":
            _print_activity_graph_status()
        else:
            raise SystemExit(f"Unknown status target '{args.target}'")
        return


def _print_activity_graph_status() -> None:
    config = get_config()
    ag_cfg = config.get("activity_graph") or {}
    slack_path = Path(ag_cfg.get("slack_graph_path") or "data/logs/slash/slack_graph.jsonl")
    git_path = Path(ag_cfg.get("git_graph_path") or "data/logs/slash/git_graph.jsonl")
    doc_path = Path(
        ag_cfg.get("doc_issues_path")
        or (config.get("activity_ingest") or {}).get("doc_issues", {}).get("path")
        or "data/live/doc_issues.json"
    )

    summary = {
        "slack_graph": _jsonl_status(slack_path, "slack"),
        "git_graph": _jsonl_status(git_path, "git"),
        "doc_issues": _doc_issues_status(doc_path),
    }
    print(json.dumps(summary, indent=2))


def _jsonl_status(path: Path, label: str) -> Dict[str, Any]:
    status: Dict[str, Any] = {"path": str(path), "label": label, "exists": path.exists()}
    if not path.exists():
        status["entries"] = 0
        status["message"] = "file not found"
        return status

    count = 0
    last_obj: Optional[Dict[str, Any]] = None
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    last_obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError as exc:  # pragma: no cover - IO errors rare
        status["error"] = str(exc)
        return status

    status["entries"] = count
    status["last_timestamp"] = _extract_timestamp(last_obj)
    status["components"] = _extract_components(last_obj)
    return status


def _doc_issues_status(path: Path) -> Dict[str, Any]:
    status: Dict[str, Any] = {"path": str(path), "label": "doc_issues", "exists": path.exists()}
    if not path.exists():
        status["entries"] = 0
        status["message"] = "file not found"
        return status

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - IO errors rare
        status["error"] = str(exc)
        return status

    try:
        payload = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        status["error"] = "failed to parse JSON"
        return status

    if isinstance(payload, dict) and "doc_issues" in payload:
        issues = payload["doc_issues"] or []
    elif isinstance(payload, list):
        issues = payload
    else:
        issues = []

    count = len(issues)
    last_issue = issues[-1] if issues else None
    status["entries"] = count
    status["last_timestamp"] = _extract_timestamp(last_issue)
    if last_issue:
        status["last_doc_id"] = last_issue.get("doc_id")
        status["last_components"] = last_issue.get("component_ids")
    return status


def _extract_timestamp(record: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    for key in ("timestamp", "ts", "last_seen", "event_ts", "updated_at", "created_at"):
        value = record.get(key)
        if not value:
            continue
        iso = _normalize_timestamp(value)
        if iso:
            return iso
    return None


def _extract_components(record: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    if not isinstance(record, dict):
        return None
    components = record.get("component_ids") or record.get("components")
    if isinstance(components, set):
        components = list(components)
    if isinstance(components, list) and components:
        return components
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        meta_components = metadata.get("component_ids") or metadata.get("components")
        if isinstance(meta_components, set):
            meta_components = list(meta_components)
        if isinstance(meta_components, list) and meta_components:
            return meta_components
    return None


def _normalize_timestamp(value: Any) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).isoformat()
        except ValueError:
            return text
    try:
        return datetime.fromtimestamp(float(value)).isoformat()
    except (TypeError, ValueError, OSError):
        return None


if __name__ == "__main__":
    main()


