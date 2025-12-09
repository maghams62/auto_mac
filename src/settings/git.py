"""Helpers for reading git monitoring overrides from settings."""
from __future__ import annotations

from typing import Dict, List, Optional

from .manager import get_global_settings_manager


def _normalize_repo_id(repo_id: str) -> str:
    return repo_id.lower().strip()


def get_git_monitor_settings(*, settings_manager=None) -> Dict[str, any]:
    manager = settings_manager or get_global_settings_manager()
    settings = manager.get_effective_settings()
    return settings.get("gitMonitor") or {}


def get_project_repos(project_id: str, *, settings_manager=None) -> List[Dict[str, str]]:
    git_monitor = get_git_monitor_settings(settings_manager=settings_manager)
    projects = git_monitor.get("projects") or {}
    return list(projects.get(project_id, []))


def resolve_repo_branch(
    repo_id: str,
    *,
    project_id: Optional[str] = None,
    fallback_branch: Optional[str] = None,
    settings_manager=None,
) -> Optional[str]:
    """Return the branch to monitor for a repo, honoring project overrides."""
    git_monitor = get_git_monitor_settings(settings_manager=settings_manager)
    default_branch = fallback_branch or git_monitor.get("defaultBranch")
    repo_key = _normalize_repo_id(repo_id)

    def _lookup(bucket: List[Dict[str, str]]) -> Optional[str]:
        for record in bucket:
            rid = record.get("repoId")
            if not rid:
                continue
            if _normalize_repo_id(rid) == repo_key:
                return record.get("branch") or default_branch
        return None

    if project_id:
        project_bucket = get_project_repos(project_id, settings_manager=settings_manager)
        branch = _lookup(project_bucket)
        if branch:
            return branch

    default_bucket = get_project_repos("default", settings_manager=settings_manager)
    branch = _lookup(default_bucket)
    if branch:
        return branch
    return default_branch

