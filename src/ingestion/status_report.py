"""
Helpers to summarize ingest health per modality (Slack, Git, doc issues).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .state import ActivityIngestState
from src.settings.runtime_mode import RuntimeFlags

SLACK_STALE_HOURS = 6
GIT_STALE_HOURS = 6
DOC_ISSUES_STALE_HOURS = 24
IMPACT_STATE_PATH = "data/state/impact_auto_ingest.json"


def build_ingest_status(config: Dict[str, Any], runtime_flags: RuntimeFlags) -> Dict[str, Any]:
    activity_cfg = config.get("activity_ingest") or {}
    state_dir = Path(activity_cfg.get("state_dir") or "data/state/activity_ingest")
    slack_cfg = activity_cfg.get("slack") or {}
    git_cfg = activity_cfg.get("git") or {}
    doc_cfg = activity_cfg.get("doc_issues") or {}
    impact_cfg = config.get("impact") or {}

    slack = _summarize_slack(state_dir, slack_cfg, runtime_flags)
    git = _summarize_git(state_dir, git_cfg, runtime_flags)
    doc_issues = _summarize_doc_issues(doc_cfg, impact_cfg, runtime_flags)

    return {
        "mode": runtime_flags.mode.value,
        "sources": {
            "slack": slack,
            "git": git,
            "doc_issues": doc_issues,
        },
    }


def _summarize_slack(
    state_dir: Path,
    slack_cfg: Dict[str, Any],
    runtime_flags: RuntimeFlags,
) -> Dict[str, Any]:
    source_mode = "live" if runtime_flags.enable_live_slack else "synthetic"
    if not slack_cfg.get("enabled"):
        return {"status": "disabled", "mode": source_mode, "channels": []}

    channels: List[Dict[str, Any]] = []
    latest_ts: Optional[datetime] = None
    channels_cfg = slack_cfg.get("channels") or []
    state = ActivityIngestState(str(state_dir))

    for channel_cfg in channels_cfg:
        channel_id = channel_cfg.get("id")
        if not channel_id:
            continue
        state_key = f"slack_{channel_id}"
        payload = state.load(state_key)
        last_ts_str = payload.get("last_ts")
        last_ts = _parse_slack_ts(last_ts_str)
        if last_ts and (latest_ts is None or last_ts > latest_ts):
            latest_ts = last_ts
        channels.append(
            {
                "id": channel_id,
                "name": channel_cfg.get("name"),
                "lastMessageAt": _iso(last_ts),
            }
        )

    status = _status_from_timestamp(latest_ts, SLACK_STALE_HOURS, source_enabled=runtime_flags.enable_live_slack or runtime_flags.enable_fixtures)

    return {
        "status": status,
        "mode": source_mode,
        "lastIngestAt": _iso(latest_ts),
        "channels": channels,
    }


def _summarize_git(
    state_dir: Path,
    git_cfg: Dict[str, Any],
    runtime_flags: RuntimeFlags,
) -> Dict[str, Any]:
    source_mode = "live" if runtime_flags.enable_live_git else "synthetic"
    if not git_cfg.get("enabled"):
        return {"status": "disabled", "mode": source_mode, "repos": []}

    repos_cfg = git_cfg.get("repos") or []
    repos: List[Dict[str, Any]] = []
    latest_commit: Optional[datetime] = None
    latest_pr: Optional[datetime] = None
    latest_issue: Optional[datetime] = None

    state = ActivityIngestState(str(state_dir))

    for repo_cfg in repos_cfg:
        owner = repo_cfg.get("owner")
        name = repo_cfg.get("name")
        if not owner or not name:
            continue
        key = f"git_{owner}_{name}"
        payload = state.load(key)
        pr_ts = _parse_iso(payload.get("last_pr_updated"))
        commit_ts = _parse_iso(payload.get("last_commit_iso"))
        issue_ts = _parse_iso(payload.get("last_issue_iso"))
        if pr_ts and (latest_pr is None or pr_ts > latest_pr):
            latest_pr = pr_ts
        if commit_ts and (latest_commit is None or commit_ts > latest_commit):
            latest_commit = commit_ts
        if issue_ts and (latest_issue is None or issue_ts > latest_issue):
            latest_issue = issue_ts
        repos.append(
            {
                "id": f"{owner}/{name}",
                "branch": repo_cfg.get("branch") or git_cfg.get("default_branch"),
                "lastCommitAt": _iso(commit_ts),
                "lastPullRequestAt": _iso(pr_ts),
                "lastIssueAt": _iso(issue_ts),
            }
        )

    latest_any = max([ts for ts in [latest_commit, latest_pr, latest_issue] if ts], default=None)
    status = _status_from_timestamp(latest_any, GIT_STALE_HOURS, source_enabled=runtime_flags.enable_live_git or runtime_flags.enable_fixtures)

    return {
        "status": status,
        "mode": source_mode,
        "lastCommitAt": _iso(latest_commit),
        "lastPullRequestAt": _iso(latest_pr),
        "lastIssueAt": _iso(latest_issue),
        "repos": repos,
    }


def _summarize_doc_issues(
    doc_cfg: Dict[str, Any],
    impact_cfg: Dict[str, Any],
    runtime_flags: RuntimeFlags,
) -> Dict[str, Any]:
    source_mode = "live" if (impact_cfg.get("data_mode", "live").lower() == "live" and runtime_flags.enable_heavy_workers) else "synthetic"
    doc_path = Path(doc_cfg.get("path") or "data/live/doc_issues.json")
    doc_file_updated_at = _file_mtime(doc_path)

    impact_state_path = Path(IMPACT_STATE_PATH)
    state_payload = _load_json_file(impact_state_path)
    repos_state = state_payload.get("repos") if isinstance(state_payload, dict) else {}
    repos: List[Dict[str, Any]] = []
    latest_run: Optional[datetime] = None

    if isinstance(repos_state, dict):
        for repo_id, info in repos_state.items():
            if not isinstance(info, dict):
                continue
            completion_ts = info.get("last_run_completed_at") or info.get("last_success_at")
            parsed_completion = _parse_iso(completion_ts)
            if parsed_completion and (latest_run is None or parsed_completion > latest_run):
                latest_run = parsed_completion
            repos.append(
                {
                    "id": repo_id,
                    "lastRunAt": _iso(parsed_completion),
                    "lastError": info.get("last_error"),
                }
            )

    status = _status_from_timestamp(latest_run or doc_file_updated_at, DOC_ISSUES_STALE_HOURS, source_enabled=doc_cfg.get("enabled", False))

    return {
        "status": status,
        "mode": source_mode,
        "lastRunAt": _iso(latest_run),
        "docIssuesFileUpdatedAt": _iso(doc_file_updated_at),
        "repos": repos,
    }


def _status_from_timestamp(
    timestamp: Optional[datetime],
    stale_hours: int,
    *,
    source_enabled: bool,
) -> str:
    if not source_enabled:
        return "disabled"
    if not timestamp:
        return "idle"
    age = datetime.now(timezone.utc) - timestamp
    if age > timedelta(hours=stale_hours):
        return "stale"
    return "ok"


def _parse_slack_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_mtime(path: Path) -> Optional[datetime]:
    if not path.exists():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except (OSError, ValueError):
        return None


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

