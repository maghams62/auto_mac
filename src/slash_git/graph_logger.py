"""
Optional graph logging for Slash Git executions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import GitQueryPlan


class SlashGitGraphLogger:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        slash_git_cfg = (config.get("slash_git") or {})
        self.enabled = bool(slash_git_cfg.get("graph_emit_enabled"))
        log_path = slash_git_cfg.get("graph_log_path", "data/logs/slash/git_graph.jsonl")
        self.log_path = Path(log_path)
        if self.enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, plan: GitQueryPlan, snapshot: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        entries = self._build_entries(plan, snapshot)
        if not entries:
            return
        with self.log_path.open("a", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry))
                handle.write("\n")

    def _build_entries(self, plan: GitQueryPlan, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        commits = snapshot.get("commits") or []
        prs = snapshot.get("prs") or []
        time_window = plan.time_window.to_dict() if plan.time_window else None

        for commit in commits:
            entries.append(
                {
                    "type": "CodeChange",
                    "repo_id": plan.repo_id,
                    "component_id": plan.component_id,
                    "sha": commit.get("sha"),
                    "author": commit.get("author"),
                    "timestamp": commit.get("timestamp"),
                    "files_changed": commit.get("files_changed", []),
                    "time_window": time_window,
                }
            )
        for pr in prs:
            entries.append(
                {
                    "type": "PullRequest",
                    "repo_id": plan.repo_id,
                    "component_id": plan.component_id,
                    "number": pr.get("number"),
                    "author": pr.get("author"),
                    "timestamp": pr.get("timestamp"),
                    "labels": pr.get("labels", []),
                    "time_window": time_window,
                }
            )

        entries.append(
            {
                "type": "ComponentImpact",
                "mode": plan.mode.value,
                "repo_id": plan.repo_id,
                "component_id": plan.component_id,
                "counts": {"commits": len(commits), "prs": len(prs)},
                "time_window": time_window,
            }
        )
        return entries

