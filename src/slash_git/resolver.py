"""
Resolver that maps parsed tokens to catalog entries and builds GitQueryPlan objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .models import (
    GitQueryMode,
    GitQueryPlan,
    GitTargetCatalog,
    GitTargetComponent,
    GitTargetRepo,
    TimeWindow,
    normalize_alias_list,
)
from ..services.git_metadata import GitMetadataService, RepoMetadata
from .parser import ParsedGitQuery


@dataclass
class GitQueryResolver:
    catalog: GitTargetCatalog
    default_repo_id: Optional[str] = None
    default_repo_days: Optional[int] = 7
    component_time_window_days: Optional[int] = 7
    metadata_service: Optional[GitMetadataService] = None

    def resolve(self, parsed: ParsedGitQuery) -> Optional[GitQueryPlan]:
        component = self._resolve_component(parsed)
        repo = self._resolve_repo(parsed, component)

        if repo is None:
            repo = self._fallback_repo()

        if repo is None:
            return None

        mode = self._resolve_mode(parsed, component)
        time_window = parsed.time_window or self._default_time_window(component)
        labels = self._derive_labels(parsed, mode)

        plan = GitQueryPlan(
            mode=mode,
            repo=repo,
            component=component,
            time_window=time_window,
            pr_number=parsed.pr_number,
            issue_ids=parsed.issue_ids,
            authors=parsed.authors,
            topic=parsed.topic,
            user_query=parsed.raw,
            labels=labels,
            keywords=parsed.keywords,
        )
        return plan

    def _resolve_mode(self, parsed: ParsedGitQuery, component: Optional[GitTargetComponent]) -> GitQueryMode:
        if parsed.pr_number is not None:
            return GitQueryMode.PR_SUMMARY
        if parsed.mode == GitQueryMode.REPO_ACTIVITY and component is not None:
            return GitQueryMode.COMPONENT_ACTIVITY
        return parsed.mode

    def _resolve_component(self, parsed: ParsedGitQuery) -> Optional[GitTargetComponent]:
        candidates: List[str] = []
        candidates.extend(parsed.entity_hints)
        candidates.extend(parsed.quoted_phrases)
        candidates.extend(parsed.keywords)
        for candidate in candidates:
            component = self.catalog.get_component(candidate)
            if component:
                return component
        # Topic-based fallback
        for token in parsed.keywords:
            normalized = token.lower()
            for repo in self.catalog.iter_repos():
                for component in repo.components.values():
                    if component.matches_topic(normalized):
                        return component
        if self.metadata_service:
            for hint in parsed.entity_hints + parsed.quoted_phrases:
                metadata_repo = self.metadata_service.find_repo(hint)
                if metadata_repo:
                    return self._metadata_repo_to_target(metadata_repo)
        return None

    def _metadata_repo_to_target(self, repo_meta: RepoMetadata) -> GitTargetRepo:
        aliases = normalize_alias_list([repo_meta.name, repo_meta.full_name, repo_meta.id])
        return GitTargetRepo(
            id=repo_meta.id,
            name=repo_meta.name,
            repo_owner=repo_meta.owner,
            repo_name=repo_meta.name,
            default_branch=repo_meta.default_branch,
            aliases=aliases,
            synthetic_root=None,
            components={},
        )

    def _resolve_repo(
        self,
        parsed: ParsedGitQuery,
        component: Optional[GitTargetComponent],
    ) -> Optional[GitTargetRepo]:
        if component:
            return self.catalog.get_repo(component.repo_id)

        for hint in parsed.entity_hints:
            repo = self.catalog.get_repo(hint)
            if repo:
                return repo
        for phrase in parsed.quoted_phrases:
            repo = self.catalog.get_repo(phrase)
            if repo:
                return repo

        return None

    def _fallback_repo(self) -> Optional[GitTargetRepo]:
        if not self.default_repo_id:
            return None
        return self.catalog.get_repo(self.default_repo_id)

    def _default_time_window(self, component: Optional[GitTargetComponent]) -> TimeWindow:
        now = datetime.now(timezone.utc)
        if component:
            if self.component_time_window_days and self.component_time_window_days > 0:
                days = self.component_time_window_days
                label = f"last {days} days (component)"
                start = now - timedelta(days=days)
                return TimeWindow(start=start, end=now, label=label, source="default")
            return TimeWindow(start=None, end=now, label="recent activity", source="default")
        if self.default_repo_days and self.default_repo_days > 0:
            days = self.default_repo_days
            label = f"last {days} days"
            start = now - timedelta(days=days)
            return TimeWindow(start=start, end=now, label=label, source="default")
        return TimeWindow(start=None, end=now, label="recent activity", source="default")

    def _derive_labels(self, parsed: ParsedGitQuery, mode: GitQueryMode) -> List[str]:
        labels: List[str] = []
        normalized_keywords = normalize_alias_list(parsed.keywords)
        if mode == GitQueryMode.ISSUE_BUG_FOCUS and "bug" in normalized_keywords:
            labels.append("bug")
        if "docs" in normalized_keywords or "documentation" in parsed.raw.lower():
            labels.append("docs")
        return labels

