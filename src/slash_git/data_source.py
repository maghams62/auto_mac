"""
Data source that feeds the Slash Git executor from synthetic fixtures.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..graph.service import GraphService
from ..services.github_pr_service import GitHubPRService
from .models import GitTargetComponent, GitTargetRepo, TimeWindow

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _matches_paths(file_paths: Sequence[str], required_patterns: Sequence[str]) -> bool:
    if not required_patterns:
        return True
    for pattern in required_patterns:
        normalized_pattern = pattern.lower()
        for file_path in file_paths:
            candidate = file_path.lower()
            if "*" in normalized_pattern or "?" in normalized_pattern:
                if fnmatch(candidate, normalized_pattern):
                    return True
            elif candidate.startswith(normalized_pattern):
                return True
    return False


def _within_window(timestamp: Optional[str], window: Optional[TimeWindow]) -> bool:
    if not window:
        return True
    dt = _parse_timestamp(timestamp)
    if not dt:
        return True
    if window.start and dt < window.start:
        return False
    if window.end and dt > window.end:
        return False
    return True


def _matches_authors(author: Optional[str], authors: Sequence[str]) -> bool:
    if not authors:
        return True
    if not author:
        return False
    author_normalized = author.lower()
    return any(author_normalized == candidate.lower() for candidate in authors)


def _matches_labels(labels: Sequence[str], required_labels: Sequence[str]) -> bool:
    if not required_labels:
        return True
    item_labels = {label.lower() for label in labels}
    return all(label.lower() in item_labels for label in required_labels)


class BaseGitDataSource:
    def get_commits(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_prs(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        pr_number: Optional[int] = None,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


@dataclass
class SyntheticGitDataSource(BaseGitDataSource):
    """Reads synthetic git commits and PRs from disk and provides filtered views."""

    events_path: Path
    prs_path: Path

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        slash_git_cfg = (config.get("slash_git") or {})
        synthetic_cfg = slash_git_cfg.get("synthetic_data") or {}
        events_path = synthetic_cfg.get("events_path", "data/synthetic_git/git_events.json")
        prs_path = synthetic_cfg.get("prs_path", "data/synthetic_git/git_prs.json")
        self.events_path = Path(events_path)
        self.prs_path = Path(prs_path)
        self._events = _load_json(self.events_path)
        self._prs = _load_json(self.prs_path)

    def get_commits(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        paths = component.paths if component else None
        authors = authors or []
        labels = labels or []
        commits: List[Dict[str, Any]] = []
        for event in self._events:
            if event.get("repo") != repo.id:
                continue
            if not _within_window(event.get("timestamp"), window):
                continue
            if authors and not _matches_authors(event.get("author"), authors):
                continue
            if labels and not _matches_labels(event.get("labels", []), labels):
                continue
            if paths:
                files = event.get("files_changed") or []
                if not _matches_paths(files, paths):
                    continue
            commits.append(event)
        return commits

    def get_prs(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        pr_number: Optional[int] = None,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        paths = component.paths if component else None
        authors = authors or []
        labels = labels or []
        prs: List[Dict[str, Any]] = []
        for pr in self._prs:
            if pr.get("repo") != repo.id:
                continue
            if pr_number is not None and pr.get("pr_number") != pr_number:
                continue
            if pr_number is None and not _within_window(pr.get("timestamp"), window):
                continue
            if authors and not _matches_authors(pr.get("author"), authors):
                continue
            if labels and not _matches_labels(pr.get("labels", []), labels):
                continue
            if paths:
                files = pr.get("files_changed") or []
                if not _matches_paths(files, paths):
                    continue
            prs.append(pr)
            if pr_number is not None:
                break
        return prs


class LiveGitDataSource(BaseGitDataSource):
    """Fetches git activity directly from GitHub via GitHubPRService."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def _service(self, repo: GitTargetRepo) -> GitHubPRService:
        return GitHubPRService(
            config=self.config,
            owner=repo.repo_owner,
            repo=repo.repo_name,
            base_branch=repo.default_branch,
        )

    def get_commits(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        service = self._service(repo)
        since = window.start.isoformat() if window and window.start else None
        until = window.end.isoformat() if window and window.end else None
        commits_data = service.list_commits(
            branch=repo.default_branch,
            since=since,
            until=until,
            include_files=True,
            per_page=50,
        )
        authors = authors or []
        paths = component.paths if component else None
        commits: List[Dict[str, Any]] = []
        for commit in commits_data:
            files = [file.get("filename") for file in commit.get("files", []) if file.get("filename")]
            repo_url = f"https://github.com/{repo.repo_owner}/{repo.repo_name}"
            record = {
                "repo": repo.id,
                "commit_sha": commit.get("sha"),
                "author": commit.get("author"),
                "timestamp": commit.get("date"),
                "message": commit.get("message"),
                "text_for_embedding": commit.get("message"),
                "files_changed": files,
                "labels": [],
                # Optional metadata for downstream deep linking
                "repo_url": repo_url,
                "url": f"{repo_url}/commit/{commit.get('sha')}" if commit.get("sha") else None,
            }
            if window and not _within_window(record["timestamp"], window):
                continue
            if authors and not _matches_authors(record.get("author"), authors):
                continue
            if paths and not _matches_paths(files, paths):
                continue
            if labels and not _matches_labels(record.get("labels", []), labels or []):
                continue
            commits.append(record)
        return commits

    def get_prs(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        pr_number: Optional[int] = None,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        service = self._service(repo)
        authors = authors or []
        paths = component.paths if component else None
        if pr_number is not None:
            pr_payload = self._fetch_single_pr(service, repo.id, pr_number, paths)
            return [pr_payload] if pr_payload else []

        prs_payload: List[Dict[str, Any]] = []
        try:
            prs = service.list_prs(state="all", base_branch=repo.default_branch, limit=15)
        except Exception:
            prs = []
        for pr in prs:
            timestamp = pr.get("merged_at") or pr.get("updated_at") or pr.get("created_at")
            if window and not _within_window(timestamp, window):
                continue
            if authors and not _matches_authors(pr.get("author"), authors):
                continue
            payload = self._fetch_single_pr(service, repo.id, pr.get("number"), paths)
            if not payload:
                continue
            if labels and not _matches_labels(payload.get("labels", []), labels):
                continue
            prs_payload.append(payload)
        return prs_payload

    def _fetch_single_pr(
        self,
        service: GitHubPRService,
        repo_id: str,
        pr_number: Optional[int],
        paths: Optional[Sequence[str]],
    ) -> Optional[Dict[str, Any]]:
        if not pr_number:
            return None
        try:
            details = service.fetch_pr_details(int(pr_number))
            diff = service.fetch_pr_diff_summary(int(pr_number))
        except Exception:
            return None
        files = [file.get("filename") for file in diff.get("files", []) if file.get("filename")]
        if paths and not _matches_paths(files, paths):
            return None
        labels = [label.get("name") for label in details.get("labels", []) if isinstance(label, dict)]
        repo_url = f"https://github.com/{service.owner}/{service.repo}"
        payload = {
            "repo": repo_id,
            "pr_number": details.get("number"),
            "title": details.get("title"),
            "body": details.get("body"),
            "author": details.get("author"),
            "timestamp": details.get("merged_at") or details.get("updated_at") or details.get("created_at"),
            "merged": bool(details.get("merged_at")),
            "labels": labels,
            "files_changed": files,
            # Optional metadata for downstream deep linking
            "repo_url": repo_url,
            "url": details.get("html_url") or (f"{repo_url}/pull/{details.get('number')}" if details.get("number") else None),
        }
        return payload


class GraphGitDataSource(BaseGitDataSource):
    """Fetches git activity from Neo4j/Qdrant ingested data."""

    _COMMIT_SOURCES = ("github_commit", "fixture_commit", "impact_commit")
    _PR_SOURCES = ("github_pr", "fixture_pr", "impact_pr")

    _COMMITS_QUERY = """
    WITH $start_iso AS startIso, $end_iso AS endIso
    MATCH (signal:ActivitySignal)
    WHERE signal.repo IN $repo_ids AND signal.source IN $sources
    OPTIONAL MATCH (signal)-[rel:SIGNALS_COMPONENT]->(component:Component)
    WITH
        signal,
        rel,
        component,
        CASE
            WHEN rel.last_seen IS NOT NULL THEN datetime(rel.last_seen)
            WHEN signal.last_seen IS NOT NULL THEN datetime(signal.last_seen)
            WHEN signal.timestamp IS NOT NULL THEN datetime(signal.timestamp)
            ELSE NULL
        END AS event_dt,
        coalesce(rel.last_seen, signal.last_seen, signal.timestamp) AS event_ts
    WHERE ($component_id IS NULL OR component.id = $component_id)
      AND (startIso IS NULL OR event_dt IS NULL OR event_dt >= datetime(startIso))
      AND (endIso IS NULL OR event_dt IS NULL OR event_dt <= datetime(endIso))
    RETURN
        signal { .* } AS signal_props,
        component.id AS component_id,
        rel.signal_weight AS signal_weight,
        event_ts AS timestamp
    ORDER BY event_dt DESC
    LIMIT $limit
    """

    _PRS_QUERY = """
    WITH $start_iso AS startIso, $end_iso AS endIso
    MATCH (pr:PR)
    WHERE pr.repo IN $repo_ids
    OPTIONAL MATCH (pr)-[:MODIFIES_COMPONENT]->(component:Component)
    WITH
        pr,
        component,
        last(split(pr.id, ":")) AS pr_number,
        CASE
            WHEN pr.updated_at IS NOT NULL THEN datetime(pr.updated_at)
            WHEN pr.created_at IS NOT NULL THEN datetime(pr.created_at)
            ELSE NULL
        END AS pr_dt,
        coalesce(pr.updated_at, pr.created_at) AS pr_ts
    WHERE ($component_id IS NULL OR component.id = $component_id)
      AND (startIso IS NULL OR pr_dt IS NULL OR pr_dt >= datetime(startIso))
      AND (endIso IS NULL OR pr_dt IS NULL OR pr_dt <= datetime(endIso))
    RETURN
        pr { .*, pr_number: pr_number } AS pr_props,
        component.id AS component_id,
        pr_ts AS timestamp
    ORDER BY pr_dt DESC
    LIMIT $limit
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        graph_service: Optional[GraphService] = None,
    ):
        self.config = config or {}
        self.graph_service = graph_service or GraphService(self.config)
        slash_git_cfg = (self.config.get("slash_git") or {})
        graph_cfg = slash_git_cfg.get("graph_mode") or {}
        limit = graph_cfg.get("max_results") or graph_cfg.get("limit") or 75
        try:
            self.result_limit = max(10, int(limit))
        except (TypeError, ValueError):
            self.result_limit = 75

    def get_commits(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._graph_available():
            return []
        component_id = component.id if component else None
        params = self._build_query_params(
            repo_ids=self._build_repo_identifiers(repo),
            component_id=component_id,
            window=window,
            sources=self._COMMIT_SOURCES,
        )
        records = self.graph_service.run_query(self._COMMITS_QUERY, params) or []
        commits: Dict[str, Dict[str, Any]] = {}
        for row in records:
            props = dict(row.get("signal_props") or {})
            signal_id = props.get("id")
            if not signal_id:
                continue
            entry = commits.setdefault(signal_id, self._build_commit_entry(props, row))
            component_ref = row.get("component_id")
            if component_ref:
                entry.setdefault("component_ids", set()).add(component_ref)
        return self._filter_commits(list(commits.values()), authors, labels or [])

    def get_prs(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: Optional[TimeWindow],
        *,
        pr_number: Optional[int] = None,
        authors: Optional[Sequence[str]] = None,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._graph_available():
            return []
        component_id = component.id if component else None
        params = self._build_query_params(
            repo_ids=self._build_repo_identifiers(repo),
            component_id=component_id,
            window=window,
            sources=self._PR_SOURCES,
        )
        records = self.graph_service.run_query(self._PRS_QUERY, params) or []
        prs: Dict[str, Dict[str, Any]] = {}
        for row in records:
            props = dict(row.get("pr_props") or {})
            pr_id = props.get("id")
            if not pr_id:
                continue
            entry = prs.setdefault(pr_id, self._build_pr_entry(props, row))
            component_ref = row.get("component_id")
            if component_ref:
                entry.setdefault("component_ids", set()).add(component_ref)
        results = self._filter_prs(list(prs.values()), pr_number, authors, labels or [])
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def available(self) -> bool:
        return bool(self.graph_service and self.graph_service.is_available())

    def _graph_available(self) -> bool:
        if not self.available():
            logger.warning("[SLASH_GIT][GRAPH] Graph service unavailable; falling back to empty snapshot")
            return False
        return True

    def _build_query_params(
        self,
        *,
        repo_ids: Sequence[str],
        component_id: Optional[str],
        window: Optional[TimeWindow],
        sources: Sequence[str],
    ) -> Dict[str, Any]:
        start_iso, end_iso = self._window_bounds(window)
        return {
            "repo_ids": list(repo_ids),
            "component_id": component_id,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "limit": self.result_limit,
            "sources": list(sources),
        }

    def _build_repo_identifiers(self, repo: GitTargetRepo) -> Sequence[str]:
        """
        Build the set of repo identifiers to use in graph queries.

        Git ingestion stores the repository as an owner/name slug (e.g. "acme/core-api")
        on ActivitySignal.repo and PR.repo, while the slash-git catalog exposes a
        logical repo id/alias (e.g. "core-api").

        To support both real GitHub ingests and synthetic/fixture data, we query using
        all known identifiers for the repo: the catalog id plus the owner/name slug
        when available.
        """
        identifiers = []
        if getattr(repo, "id", None):
            identifiers.append(repo.id)
        owner = getattr(repo, "repo_owner", None)
        name = getattr(repo, "repo_name", None)
        if owner and name:
            identifiers.append(f"{owner}/{name}")
        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for value in identifiers:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped

    def _build_commit_entry(self, props: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        files = props.get("files") or props.get("files_changed") or []
        labels = props.get("labels") or []
        return {
            "id": props.get("id"),
            "repo": props.get("repo"),
            "commit_sha": props.get("sha") or props.get("commit_sha"),
            "author": props.get("author"),
            "timestamp": row.get("timestamp") or props.get("timestamp"),
            "message": props.get("message") or props.get("title"),
            "text_for_embedding": props.get("text_for_embedding") or props.get("message"),
            "files_changed": files,
            "labels": labels,
            "repo_url": props.get("repo_url"),
            "url": props.get("url"),
        }

    def _build_pr_entry(self, props: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        files = props.get("files") or props.get("files_changed") or []
        labels = props.get("labels") or []
        pr_number = props.get("pr_number") or self._extract_pr_number(props.get("id"))
        return {
            "id": props.get("id"),
            "repo": props.get("repo"),
            "pr_number": self._coerce_int(pr_number),
            "title": props.get("title"),
            "body": props.get("body"),
            "author": props.get("author"),
            "timestamp": row.get("timestamp") or props.get("updated_at") or props.get("created_at"),
            "merged": props.get("merged"),
            "labels": labels,
            "files_changed": files,
            "repo_url": props.get("url_root") or props.get("repo_url"),
            "url": props.get("url"),
        }

    def _filter_commits(
        self,
        commits: List[Dict[str, Any]],
        authors: Optional[Sequence[str]],
        labels: Sequence[str],
    ) -> List[Dict[str, Any]]:
        author_filter = list(authors or [])
        label_filter = list(labels or [])
        filtered: List[Dict[str, Any]] = []
        for commit in commits:
            if author_filter and not _matches_authors(commit.get("author"), author_filter):
                continue
            if label_filter and not _matches_labels(commit.get("labels", []), label_filter):
                continue
            commit.pop("component_ids", None)
            filtered.append(commit)
        return filtered

    def _filter_prs(
        self,
        prs: List[Dict[str, Any]],
        pr_number: Optional[int],
        authors: Optional[Sequence[str]],
        labels: Sequence[str],
    ) -> List[Dict[str, Any]]:
        author_filter = list(authors or [])
        label_filter = list(labels or [])
        filtered: List[Dict[str, Any]] = []
        for pr in prs:
            if pr_number is not None and pr.get("pr_number") != pr_number:
                continue
            if author_filter and not _matches_authors(pr.get("author"), author_filter):
                continue
            if label_filter and not _matches_labels(pr.get("labels", []), label_filter):
                continue
            pr.pop("component_ids", None)
            filtered.append(pr)
        return filtered

    def _window_bounds(self, window: Optional[TimeWindow]) -> tuple[Optional[str], Optional[str]]:
        if not window:
            return None, None
        return self._isoformat(window.start), self._isoformat(window.end)

    @staticmethod
    def _isoformat(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        if not value.tzinfo:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _extract_pr_number(pr_id: Optional[str]) -> Optional[int]:
        if not pr_id:
            return None
        tokens = pr_id.split(":")
        if not tokens:
            return None
        tail = tokens[-1]
        try:
            return int(tail)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

