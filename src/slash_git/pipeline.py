"""
Slash Git pipeline orchestrating planning, execution, and graph logging.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional

from .data_source import (
    BaseGitDataSource,
    GraphGitDataSource,
    LiveGitDataSource,
    SyntheticGitDataSource,
)
from .executor import GitQueryExecutor
from .graph_logger import SlashGitGraphLogger
from .models import GitQueryPlan, TimeWindow
from .planner import GitQueryPlanner
from ..services.git_metadata import GitMetadataService

logger = logging.getLogger(__name__)


@dataclass
class SlashGitPipelineResult:
    plan: GitQueryPlan
    snapshot: Dict[str, Any]


class SlashGitPipeline:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        metadata_service: Optional[GitMetadataService] = None,
        data_source: Optional[BaseGitDataSource] = None,
    ):
        self.config = config or {}
        self.planner = GitQueryPlanner(self.config, metadata_service=metadata_service)
        self.data_source = data_source or self._build_data_source()
        self.executor = GitQueryExecutor(self.config, self.planner.catalog, data_source=self.data_source)
        self.graph_logger = SlashGitGraphLogger(self.config)

    def run(self, command: str) -> Optional[SlashGitPipelineResult]:
        plan = self.planner.plan(command)
        if not plan:
            return None
        snapshot = self.executor.run(plan)
        extended_plan = self._maybe_extend_time_window(plan, snapshot)
        if extended_plan is not plan:
            plan = extended_plan
            snapshot = self.executor.run(plan)
        self.graph_logger.emit(plan, snapshot)
        return SlashGitPipelineResult(plan=plan, snapshot=snapshot)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_data_source(self) -> BaseGitDataSource:
        slash_git_cfg = self.config.get("slash_git") or {}
        env_mode = os.getenv("SLASH_GIT_DATA_MODE")
        configured_mode = slash_git_cfg.get("data_mode")
        mode = (env_mode or configured_mode or "").strip().lower()
        if not mode:
            mode = "live" if slash_git_cfg.get("use_live_data") else "graph"

        if mode in {"live", "github"}:
            return LiveGitDataSource(self.config)
        if mode in {"synthetic", "fixture", "fixtures"}:
            return SyntheticGitDataSource(self.config)

        # Default to graph-backed data source with optional fallback.
        graph_data_source = GraphGitDataSource(self.config)
        graph_cfg = slash_git_cfg.get("graph_mode")
        graph_required = bool((graph_cfg or {}).get("require", False))
        if graph_data_source.available():
            return graph_data_source

        if graph_required:
            raise RuntimeError(
                "[SLASH_GIT] Graph data mode required but Neo4j is unavailable; "
                "set slash_git.graph_mode.require=false or SLASH_GIT_DATA_MODE=synthetic to override."
            )

        logger.warning("[SLASH_GIT] Graph mode unavailable, falling back to synthetic fixtures")
        return SyntheticGitDataSource(self.config)

    def _maybe_extend_time_window(self, plan: GitQueryPlan, snapshot: Dict[str, Any]) -> GitQueryPlan:
        """If the default window produced no activity, re-run with an open window."""
        if not plan.time_window:
            return plan
        if plan.time_window.source != "default":
            return plan
        if plan.time_window.start is None and plan.time_window.end is None:
            # Already unbounded; nothing to extend.
            return plan
        if self._snapshot_has_activity(snapshot):
            return plan

        fallback_window = TimeWindow(
            start=None,
            end=None,
            label="recent activity (auto-extended)",
            source="fallback_recent",
        )
        return replace(plan, time_window=fallback_window)

    @staticmethod
    def _snapshot_has_activity(snapshot: Dict[str, Any]) -> bool:
        if not isinstance(snapshot, dict):
            return False
        commits = snapshot.get("commits") or []
        prs = snapshot.get("prs") or []
        return bool(commits or prs)

