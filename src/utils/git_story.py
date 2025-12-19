"""
Utilities for generating themed Git story entries used by slash-git tests.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple


STORY_FILE_RELATIVE = Path("tests/data/git_story.md")

SUBSYSTEMS = [
    "telemetry-ingest",
    "queue-drain",
    "sensor-fusion",
    "alert-router",
    "sla-guardian",
]

EVENTS = [
    "calibrated heartbeat",
    "replayed backlog",
    "patched drift report",
    "normalized jitter",
    "recolored burn chart",
]

METRICS = [
    "latency",
    "throughput",
    "error-rate",
    "fanout",
    "payload-size",
]

FOLLOW_UPS = [
    "queued a shadow run",
    "emailed ops for review",
    "flagged the scenario for slash-git demo",
    "wired the change into graph ingest",
    "pinned the commit for telemetry audit",
]

BRANCH_HINT_KEYS: Sequence[Sequence[str]] = (
    ("slash_git", "test_branch"),
    ("github", "test_branch"),
)


def build_story_entry(seed: Optional[int] = None) -> Tuple[str, str]:
    """
    Construct a single markdown bullet describing the latest telemetry beat.

    Returns:
        tuple: (markdown_line, headline_for_commit_message)
    """
    rng = random.Random(seed)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    subsystem = rng.choice(SUBSYSTEMS)
    event = rng.choice(EVENTS)
    metric = rng.choice(METRICS)
    impact = rng.uniform(0.5, 6.0)
    follow_up = rng.choice(FOLLOW_UPS)

    headline = f"{subsystem} {event} {metric}"
    line = (
        f"- {timestamp} | subsystem `{subsystem}` {event} "
        f"{metric} window by ±{impact:.1f}% and {follow_up}."
    )
    return line, headline


def discover_story_branch(
    config: Dict[str, Any],
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    override: Optional[str] = None,
) -> str:
    """
    Determine which branch should receive the synthetic commits.
    """
    if override:
        return override

    for path in BRANCH_HINT_KEYS:
        current = config
        for key in path:
            current = current.get(key) if isinstance(current, dict) else None
        if isinstance(current, str) and current.strip():
            return current

    github_cfg = config.get("github") or {}
    owner = repo_owner or github_cfg.get("repo_owner")
    name = repo_name or github_cfg.get("repo_name")

    activity_cfg = (
        config.get("activity_ingest", {})
        .get("git", {})
        .get("repos", [])
    )
    for repo in activity_cfg:
        if repo.get("owner") == owner and repo.get("name") == name and repo.get("branch"):
            return repo["branch"]

    return github_cfg.get("base_branch", "main")


def ensure_story_file_exists(repo_root: Path) -> Path:
    """
    Make sure the shared story ledger exists and has a header.
    """
    story_path = repo_root / STORY_FILE_RELATIVE
    if not story_path.exists():
        story_path.parent.mkdir(parents=True, exist_ok=True)
        story_path.write_text(
            "# Telemetry Story Log\n\n"
            "This log powers slash-git demos. Each entry chronicles a small "
            "telemetry tweak so `/git` queries always have fresh, coherent data.\n\n"
        )
    return story_path

