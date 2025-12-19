"""
Shared dataclasses for the Slash Git pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml

from ..utils import _expand_env_vars


def _normalize_alias(value: str) -> str:
    token = value.strip().lower()
    token = token.replace("_", " ")
    token = re.sub(r"[^a-z0-9]+", " ", token)
    token = re.sub(r"\s+", " ", token).strip()
    return token


def _alias_keys(value: str) -> List[str]:
    base = _normalize_alias(value)
    if not base:
        return []
    keys = {base}
    keys.add(base.replace(" ", "-"))
    keys.add(base.replace(" ", ""))
    return list(keys)


def _normalize_aliases(values: Sequence[str]) -> List[str]:
    keys: List[str] = []
    seen = set()
    for value in values:
        for key in _alias_keys(value):
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def normalize_alias_token(value: str) -> str:
    """Shared alias normalizer (public wrapper)."""
    return _normalize_alias(value)


def alias_key_variants(value: str) -> List[str]:
    """Public helper mirroring internal alias key generation."""
    return _alias_keys(value)


def normalize_alias_list(values: Sequence[str]) -> List[str]:
    """Public helper returning normalized alias list."""
    return _normalize_aliases(values)


@dataclass
class TimeWindow:
    """Represents an absolute time window."""

    start: Optional[datetime] = None
    end: Optional[datetime] = None
    label: str = "recent"
    source: str = "default"

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "label": self.label,
            "source": self.source,
        }


class GitQueryMode(str, Enum):
    REPO_ACTIVITY = "repo_activity"
    COMPONENT_ACTIVITY = "component_activity"
    PR_SUMMARY = "pr_summary"
    ISSUE_BUG_FOCUS = "issue_bug_focus"
    AUTHOR_FOCUS = "author_focus"


@dataclass
class GitTargetComponent:
    """Canonical component description."""

    id: str
    name: str
    repo_id: str
    project_id: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    topic_aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, repo_id: str, data: Dict[str, Any]) -> "GitTargetComponent":
        topics = list(data.get("topics") or [])
        return cls(
            id=data["id"],
            name=data.get("name") or data["id"],
            repo_id=repo_id,
            project_id=data.get("project_id"),
            aliases=_normalize_aliases(data.get("aliases", [])) or _alias_keys(data["id"]),
            paths=list(data.get("paths") or []),
            topics=topics,
            topic_aliases=_normalize_aliases(topics),
            metadata={
                k: v
                for k, v in data.items()
                if k not in {"id", "name", "aliases", "paths", "topics", "project_id"}
            },
        )

    def matches_topic(self, token: str) -> bool:
        normalized = normalize_alias_token(token)
        return normalized in self.topic_aliases or normalized in self.aliases


@dataclass
class GitTargetRepo:
    """Canonical repository description."""

    id: str
    name: str
    repo_owner: str
    repo_name: str
    default_branch: str
    aliases: List[str] = field(default_factory=list)
    synthetic_root: Optional[str] = None
    components: Dict[str, GitTargetComponent] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GitTargetRepo":
        repo_id = data["id"]
        components: Dict[str, GitTargetComponent] = {}
        for comp_data in data.get("components", []):
            component = GitTargetComponent.from_dict(repo_id, comp_data)
            components[component.id] = component

        return cls(
            id=repo_id,
            name=data.get("name") or repo_id,
            repo_owner=data.get("repo_owner") or "",
            repo_name=data.get("repo_name") or repo_id,
            default_branch=data.get("default_branch") or "main",
            aliases=_normalize_aliases(data.get("aliases", [])) or _alias_keys(repo_id),
            synthetic_root=data.get("synthetic_root"),
            components=components,
        )

    def find_component(self, component_id_or_alias: Optional[str]) -> Optional[GitTargetComponent]:
        if not component_id_or_alias:
            return None
        key = _normalize_alias(component_id_or_alias)
        if component_id_or_alias in self.components:
            return self.components[component_id_or_alias]
        for component in self.components.values():
            if key in component.aliases or key == component.id:
                return component
        return None


@dataclass
class GitTargetCatalog:
    """In-memory representation of slash git targets."""

    repos: Dict[str, GitTargetRepo] = field(default_factory=dict)
    repo_aliases: Dict[str, str] = field(default_factory=dict)
    component_aliases: Dict[str, str] = field(default_factory=dict)

    _PLACEHOLDER_PATTERN = re.compile(r"\$\{[^}]+\}")

    @classmethod
    def from_file(cls, path: Path | str) -> "GitTargetCatalog":
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Slash Git target catalog missing at {path_obj}")
        payload = yaml.safe_load(path_obj.read_text()) or {}
        payload = _expand_env_vars(payload)
        repos_data = payload.get("repos") or []

        repos: Dict[str, GitTargetRepo] = {}
        repo_aliases: Dict[str, str] = {}
        component_aliases: Dict[str, str] = {}

        for repo_entry in repos_data:
            cls._validate_repo_entry(repo_entry)
            repo = GitTargetRepo.from_dict(repo_entry)
            repos[repo.id] = repo
            for alias in repo.aliases:
                repo_aliases.setdefault(alias, repo.id)
            for component in repo.components.values():
                component_aliases.setdefault(component.id, component.id)
                for alias in component.aliases:
                    component_aliases.setdefault(alias, component.id)

        return cls(repos=repos, repo_aliases=repo_aliases, component_aliases=component_aliases)

    def get_repo(self, identifier: Optional[str]) -> Optional[GitTargetRepo]:
        if not identifier:
            return None
        if identifier in self.repos:
            return self.repos[identifier]
        key = _normalize_alias(identifier)
        repo_id = self.repo_aliases.get(key)
        if repo_id:
            return self.repos.get(repo_id)
        return None

    def get_component(self, identifier: Optional[str]) -> Optional[GitTargetComponent]:
        if not identifier:
            return None
        if identifier in self.component_aliases:
            component_id = self.component_aliases[identifier]
        else:
            component_id = self.component_aliases.get(_normalize_alias(identifier))
        if not component_id:
            return None
        for repo in self.repos.values():
            component = repo.components.get(component_id)
            if component:
                return component
        return None

    def iter_repos(self) -> Iterable[GitTargetRepo]:
        return self.repos.values()

    @classmethod
    def _validate_repo_entry(cls, repo_entry: Dict[str, Any]) -> None:
        repo_label = repo_entry.get("id") or repo_entry.get("name") or "<repo>"
        cls._ensure_no_placeholder(repo_entry.get("repo_owner"), f"{repo_label}.repo_owner")
        cls._ensure_no_placeholder(repo_entry.get("repo_name"), f"{repo_label}.repo_name")
        cls._ensure_no_placeholder(repo_entry.get("default_branch"), f"{repo_label}.default_branch")
        for alias in repo_entry.get("aliases") or []:
            cls._ensure_no_placeholder(alias, f"{repo_label}.aliases")

        for component_entry in repo_entry.get("components") or []:
            comp_label = component_entry.get("id") or component_entry.get("name") or "<component>"
            cls._ensure_no_placeholder(component_entry.get("id"), f"{repo_label}.{comp_label}.id")
            for alias in component_entry.get("aliases") or []:
                cls._ensure_no_placeholder(alias, f"{repo_label}.{comp_label}.aliases")
            for path_value in component_entry.get("paths") or []:
                cls._ensure_no_placeholder(path_value, f"{repo_label}.{comp_label}.paths")

    @classmethod
    def _ensure_no_placeholder(cls, value: Any, context: str) -> None:
        if isinstance(value, str) and cls._PLACEHOLDER_PATTERN.search(value):
            raise ValueError(f"Slash Git target '{context}' contains unresolved placeholder: {value}")


@dataclass
class GitQueryPlan:
    """Structured instructions for executing a /git query."""

    mode: GitQueryMode
    repo: Optional[GitTargetRepo] = None
    component: Optional[GitTargetComponent] = None
    time_window: Optional[TimeWindow] = None
    pr_number: Optional[int] = None
    issue_ids: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    user_query: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    @property
    def repo_id(self) -> Optional[str]:
        return self.repo.id if self.repo else None

    @property
    def component_id(self) -> Optional[str]:
        return self.component.id if self.component else None

