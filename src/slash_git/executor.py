"""
Executes GitQueryPlan objects against the configured data source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .data_source import BaseGitDataSource, SyntheticGitDataSource
from .models import GitQueryMode, GitQueryPlan, GitTargetCatalog


def _short_sha(sha: Optional[str]) -> Optional[str]:
    if not sha:
        return None
    return sha[:7]


@dataclass
class GitQueryExecutor:
    config: Dict[str, Any]
    catalog: GitTargetCatalog
    data_source: Optional[BaseGitDataSource] = None

    def __post_init__(self) -> None:
        if self.data_source is None:
            self.data_source = SyntheticGitDataSource(self.config)

    def run(self, plan: GitQueryPlan) -> Dict[str, Any]:
        if not plan.repo:
            raise ValueError("GitQueryExecutor requires the plan to include a repository.")

        repo = plan.repo
        component = plan.component
        time_window = plan.time_window

        commits_raw = self.data_source.get_commits(
            repo=repo,
            component=component,
            window=time_window,
            authors=plan.authors,
            labels=plan.labels,
        )
        prs_raw = self.data_source.get_prs(
            repo=repo,
            component=component,
            window=time_window,
            pr_number=plan.pr_number if plan.mode == GitQueryMode.PR_SUMMARY else None,
            authors=plan.authors,
            labels=plan.labels,
        )

        snapshot = {
            "commits": [self._normalize_commit(commit, plan) for commit in self._sort_by_timestamp(commits_raw)],
            "prs": [self._normalize_pr(pr, plan) for pr in self._sort_by_timestamp(prs_raw)],
            "issues": [],
            "meta": {
                "repo_id": plan.repo_id,
                "component_id": plan.component_id,
                "mode": plan.mode.value,
                "time_window": time_window.to_dict() if time_window else None,
                "authors": plan.authors,
                "labels": plan.labels,
                "topic": plan.topic,
            },
        }
        return snapshot

    def _sort_by_timestamp(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(items, key=lambda item: item.get("timestamp") or "", reverse=True)

    def _normalize_commit(self, commit: Dict[str, Any], plan: GitQueryPlan) -> Dict[str, Any]:
        sha = commit.get("commit_sha") or commit.get("id")
        return {
            "sha": sha,
            "short_sha": _short_sha(sha),
            "author": commit.get("author"),
            "timestamp": commit.get("timestamp"),
            "title": commit.get("message") or commit.get("text_for_embedding"),
            "message": commit.get("message"),
            "files_changed": commit.get("files_changed", []),
            "labels": commit.get("labels", []),
            "repo": commit.get("repo"),
            # Optional link and metadata fields preserved from the data source
            # so that downstream consumers (traceability, UI deep links) can
            # construct stable URLs or evidence identifiers without guessing.
            "id": commit.get("id"),
            "repo_url": commit.get("repo_url"),
            "url": commit.get("url"),
            "component_id": plan.component_id,
        }

    def _normalize_pr(self, pr: Dict[str, Any], plan: GitQueryPlan) -> Dict[str, Any]:
        return {
            "number": pr.get("pr_number"),
            "title": pr.get("title"),
            "author": pr.get("author"),
            "timestamp": pr.get("timestamp"),
            "merged": pr.get("merged", True),
            "merged_at": pr.get("timestamp") if pr.get("merged") else None,
            "labels": pr.get("labels", []),
            "files_changed": pr.get("files_changed", []),
            "body": pr.get("body"),
            "repo": pr.get("repo"),
            # Optional link/metadata fields carried through for deep links.
            "repo_url": pr.get("repo_url"),
            "url": pr.get("url"),
            "component_id": plan.component_id,
        }

