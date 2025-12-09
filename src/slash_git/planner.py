"""
High-level planner combining the parser and resolver into a single entrypoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .models import GitQueryPlan, GitTargetCatalog
from ..services.git_metadata import GitMetadataService
from .parser import GitQueryParser
from .resolver import GitQueryResolver


class GitQueryPlanner:
    """Facade that produces GitQueryPlan objects from raw /git prompts."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, *, metadata_service: Optional[GitMetadataService] = None):
        config = config or {}
        slash_git_cfg = (config.get("slash_git") or {}).copy()
        catalog_path = slash_git_cfg.get("target_catalog_path") or "config/slash_git_targets.yaml"
        default_repo_id = slash_git_cfg.get("default_repo_id")
        default_days_raw = slash_git_cfg.get("default_time_window_days", 7)
        component_days_raw = slash_git_cfg.get("component_time_window_days", default_days_raw)
        try:
            default_days = int(default_days_raw)
        except (TypeError, ValueError):
            default_days = 0
        try:
            component_days = int(component_days_raw)
        except (TypeError, ValueError):
            component_days = default_days

        catalog = GitTargetCatalog.from_file(Path(catalog_path))
        self.catalog = catalog
        self.parser = GitQueryParser(default_days=default_days)
        self.resolver = GitQueryResolver(
            catalog=catalog,
            default_repo_id=default_repo_id,
            default_repo_days=default_days if default_days > 0 else None,
            component_time_window_days=component_days if component_days > 0 else None,
            metadata_service=metadata_service,
        )

    def plan(self, command: str) -> Optional[GitQueryPlan]:
        if not command or not command.strip():
            return None
        try:
            parsed = self.parser.parse(command)
        except ValueError:
            return None
        plan = self.resolver.resolve(parsed)
        return plan

