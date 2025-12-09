"""
Git metadata provider backed by GitHub REST APIs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml

from .ttl_cache import TTLCache, CacheStats
from ..services.github_pr_service import GitHubAPIError, GitHubPRService
from ..settings.git import get_git_monitor_settings
from ..slash_git.models import GitTargetCatalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepoMetadata:
    id: str
    owner: str
    name: str
    full_name: str
    default_branch: str
    description: Optional[str]
    topics: Sequence[str]


@dataclass(frozen=True)
class BranchMetadata:
    name: str
    is_default: bool
    protected: bool


class GitMetadataService:
    """
    Cache GitHub repo/branch metadata for slash-command autocomplete flows.
    """

    REPO_CACHE_KEY = "repos"

    def __init__(self, config: Optional[Dict[str, any]] = None):
        self.config = config or {}
        metadata_cfg = (self.config.get("metadata_cache") or {}).get("git") or {}
        repo_ttl = int(metadata_cfg.get("repo_ttl_seconds", 900))
        branch_ttl = int(metadata_cfg.get("branch_ttl_seconds", 300))
        self.max_branches = int(metadata_cfg.get("max_branches_per_repo", 500))
        self.log_metrics = bool(metadata_cfg.get("log_metrics", False))
        self.repo_cache = TTLCache(repo_ttl, label="git_repos")
        self.branch_cache: Dict[str, TTLCache] = {}
        self._service_cache: Dict[str, GitHubPRService] = {}
        self.repo_targets = self._collect_repo_targets()
        graph_cfg = (self.config.get("slash_git") or {}).get("graph_mode") or {}
        self.graph_only_mode = bool(graph_cfg.get("require", False))
        self._graph_catalog: Optional[GitTargetCatalog] = None
        if self.graph_only_mode:
            catalog_path = (self.config.get("slash_git") or {}).get("target_catalog_path")
            if catalog_path and Path(catalog_path).exists():
                try:
                    self._graph_catalog = GitTargetCatalog.from_file(catalog_path)
                except Exception as exc:
                    logger.warning("[GIT METADATA] Failed to load graph catalog at %s: %s", catalog_path, exc)

    # ------------------------------------------------------------------ #
    # Repo helpers
    # ------------------------------------------------------------------ #
    def list_repos(self, prefix: str = "", limit: int = 10) -> List[RepoMetadata]:
        payload = self._ensure_repos()
        repos: List[RepoMetadata] = payload["items"]
        if not prefix:
            return repos[: limit or len(repos)]
        prefix_lower = prefix.lower()
        results: List[RepoMetadata] = []
        for repo in repos:
            if len(results) >= limit:
                break
            if (
                repo.id.lower().startswith(prefix_lower)
                or repo.name.lower().startswith(prefix_lower)
                or repo.full_name.lower().startswith(prefix_lower)
            ):
                results.append(repo)
        return results

    def find_repo(self, identifier: Optional[str]) -> Optional[RepoMetadata]:
        if not identifier:
            return None
        payload = self._ensure_repos()
        lookup = payload["aliases"]
        key = identifier.lower()
        repo = lookup.get(identifier) or lookup.get(key)
        if repo:
            return repo
        if "/" in identifier:
            owner, name = identifier.split("/", 1)
            repo = self._fetch_repo(owner, name)
            if repo:
                self._merge_repo(repo)
                return repo
        return None

    def refresh_repos(self, *, force: bool = False) -> List[RepoMetadata]:
        if force:
            self.repo_cache.invalidate(self.REPO_CACHE_KEY)
        payload = self._ensure_repos()
        return payload["items"]

    # ------------------------------------------------------------------ #
    # Branch helpers
    # ------------------------------------------------------------------ #
    def list_branches(
        self,
        repo_identifier: str,
        prefix: str = "",
        limit: int = 10,
    ) -> List[BranchMetadata]:
        cache = self._branch_cache_for(repo_identifier)
        payload = cache.get(repo_identifier)
        if not payload:
            repo_meta = self.find_repo(repo_identifier)
            if not repo_meta:
                return []
            branches = self._fetch_branches(repo_meta)
            payload = {"items": branches}
            cache.set(repo_identifier, payload)
            self._log_cache_stats(f"git_branches:{repo_identifier}", cache.describe())
        else:
            self._log_cache_stats(f"git_branches:{repo_identifier}", cache.describe())
        branches: List[BranchMetadata] = payload["items"]
        if not prefix:
            return branches[: limit or len(branches)]
        prefix_lower = prefix.lower()
        results: List[BranchMetadata] = []
        for branch in branches:
            if len(results) >= limit:
                break
            if branch.name.lower().startswith(prefix_lower):
                results.append(branch)
        return results

    def refresh_branches(self, repo_identifier: str, *, force: bool = False) -> List[BranchMetadata]:
        cache = self._branch_cache_for(repo_identifier)
        if force:
            cache.invalidate(repo_identifier)
        repo_meta = self.find_repo(repo_identifier)
        if not repo_meta:
            return []
        branches = self._fetch_branches(repo_meta)
        cache.set(repo_identifier, {"items": branches})
        return branches

    def suggest_branches(
        self,
        repo_identifier: str,
        prefix: str = "",
        limit: int = 5,
    ) -> List[str]:
        branches = self.list_branches(repo_identifier, prefix=prefix, limit=max(limit * 2, 25))
        names = [branch.name for branch in branches]
        if not prefix:
            return names[:limit]
        prefix_lower = prefix.lower()
        direct = [name for name in names if name.lower().startswith(prefix_lower)]
        if direct:
            return direct[:limit]
        universe = self.list_branches(repo_identifier, prefix="", limit=max(limit * 4, 50))
        universe_names = [branch.name for branch in universe]
        close = difflib.get_close_matches(prefix, universe_names, n=limit, cutoff=0.55)
        return close

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #
    def describe(self) -> Dict[str, any]:
        return {
            "repos": self.repo_cache.describe().__dict__,
            "branch_caches": {
                repo_id: cache.describe().__dict__ for repo_id, cache in self.branch_cache.items()
            },
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_repos(self) -> Dict[str, any]:
        if self.graph_only_mode and self._graph_catalog:
            return self._catalog_repo_payload()
        payload = self.repo_cache.get(self.REPO_CACHE_KEY)
        if payload:
            self._log_cache_stats("git_repos", self.repo_cache.describe())
            return payload
        repos: List[RepoMetadata] = []
        aliases: Dict[str, RepoMetadata] = {}
        for owner, name in self.repo_targets:
            repo = self._fetch_repo(owner, name)
            if not repo:
                continue
            repos.append(repo)
            aliases[repo.id] = repo
            aliases[repo.id.lower()] = repo
            aliases[repo.name.lower()] = repo
            aliases[repo.full_name.lower()] = repo
        payload = {"items": repos, "aliases": aliases}
        self.repo_cache.set(self.REPO_CACHE_KEY, payload)
        self._log_cache_stats("git_repos", self.repo_cache.describe())
        return payload

    def _merge_repo(self, repo: RepoMetadata) -> None:
        payload = self._ensure_repos()
        aliases: Dict[str, RepoMetadata] = payload["aliases"]
        aliases[repo.id] = repo
        aliases[repo.id.lower()] = repo
        aliases[repo.name.lower()] = repo
        aliases[repo.full_name.lower()] = repo
        items: List[RepoMetadata] = payload["items"]
        if all(existing.id != repo.id for existing in items):
            items.append(repo)
        self.repo_cache.set(self.REPO_CACHE_KEY, {"items": items, "aliases": aliases})

    def _fetch_repo(self, owner: str, name: str) -> Optional[RepoMetadata]:
        if self.graph_only_mode:
            return None
        service = self._service_for(owner, name)
        try:
            info = service.get_repo_info(force_refresh=True)
        except GitHubAPIError as exc:
            logger.warning("Failed to fetch repo %s/%s: %s", owner, name, exc)
            return None
        repo = RepoMetadata(
            id=f"{owner}/{name}",
            owner=owner,
            name=name,
            full_name=info.get("full_name") or f"{owner}/{name}",
            default_branch=info.get("default_branch") or "main",
            description=info.get("description"),
            topics=tuple(info.get("topics", [])),
        )
        return repo

    def _fetch_branches(self, repo: RepoMetadata) -> List[BranchMetadata]:
        if self.graph_only_mode:
            return [
                BranchMetadata(
                    name=repo.default_branch,
                    is_default=True,
                    protected=False,
                )
            ]
        service = self._service_for(repo.owner, repo.name)
        branches: List[BranchMetadata] = []
        try:
            raw = service.list_branches(names_only=False, limit=self.max_branches)
            for entry in raw:
                if isinstance(entry, str):
                    branches.append(
                        BranchMetadata(
                            name=entry,
                            is_default=entry == repo.default_branch,
                            protected=False,
                        )
                    )
                else:
                    branches.append(
                        BranchMetadata(
                            name=entry.get("name"),
                            is_default=entry.get("is_default", False),
                            protected=entry.get("protected", False),
                        )
                    )
        except GitHubAPIError as exc:
            logger.warning("Failed to list branches for %s: %s", repo.id, exc)
        return branches[: self.max_branches] if self.max_branches else branches

    def _branch_cache_for(self, repo_identifier: str) -> TTLCache:
        cache = self.branch_cache.get(repo_identifier)
        if cache:
            return cache
        ttl = (self.config.get("metadata_cache") or {}).get("git", {}).get("branch_ttl_seconds", 300)
        cache = TTLCache(int(ttl), label=f"git_branches:{repo_identifier}")
        self.branch_cache[repo_identifier] = cache
        return cache

    def _service_for(self, owner: str, name: str) -> GitHubPRService:
        if self.graph_only_mode:
            raise RuntimeError("Live GitHub metadata requests are disabled in graph-only mode.")
        key = f"{owner}/{name}"
        service = self._service_cache.get(key)
        if not service:
            service = GitHubPRService(
                config=self.config,
                owner=owner,
                repo=name,
            )
            self._service_cache[key] = service
        return service

    def _collect_repo_targets(self) -> List[Tuple[str, str]]:
        targets: Set[Tuple[str, str]] = set()
        github_cfg = self.config.get("github") or {}
        owner = github_cfg.get("repo_owner")
        name = github_cfg.get("repo_name")
        if owner and name:
            targets.add((owner, name))

        activity_cfg = (self.config.get("activity_ingest") or {}).get("git") or {}
        for repo in activity_cfg.get("repos", []):
            repo_owner = repo.get("owner") or repo.get("repo_owner")
            repo_name = repo.get("name") or repo.get("repo_name")
            if repo_owner and repo_name:
                targets.add((repo_owner, repo_name))

        catalog_path = (self.config.get("slash_git") or {}).get("target_catalog_path")
        if catalog_path:
            try:
                payload = yaml.safe_load(Path(catalog_path).read_text()) or {}
                for repo in payload.get("repos", []):
                    repo_owner = repo.get("repo_owner")
                    repo_name = repo.get("repo_name")
                    if repo_owner and repo_name:
                        targets.add((repo_owner, repo_name))
            except Exception as exc:
                logger.debug("Unable to read slash git catalog for metadata targets: %s", exc)

        try:
            git_monitor = get_git_monitor_settings()
            for project_overrides in git_monitor.get("projects", {}).values():
                for record in project_overrides:
                    repo_id = record.get("repoId")
                    if not repo_id or "/" not in repo_id:
                        continue
                    owner, repo_name = repo_id.split("/", 1)
                    targets.add((owner, repo_name))
        except Exception as exc:  # pragma: no cover - settings access rare failure
            logger.debug("Unable to read settings git monitor targets: %s", exc)

        return sorted(targets)

    def _log_cache_stats(self, label: str, stats: CacheStats) -> None:
        if not self.log_metrics:
            return
        logger.info(
            "[METADATA] %s cache hits=%s misses=%s size=%s ttl=%ss",
            label,
            stats.hits,
            stats.misses,
            stats.size,
            stats.ttl_seconds,
        )

    def _catalog_repo_payload(self) -> Dict[str, Any]:
        if not self._graph_catalog:
            return {"items": [], "aliases": {}}
        repos: List[RepoMetadata] = []
        aliases: Dict[str, RepoMetadata] = {}
        for repo in self._graph_catalog.iter_repos():
            repo_id = repo.id or f"{repo.repo_owner}/{repo.repo_name}"
            metadata = RepoMetadata(
                id=repo_id,
                owner=repo.repo_owner,
                name=repo.repo_name,
                full_name=f"{repo.repo_owner}/{repo.repo_name}",
                default_branch=repo.default_branch or "main",
                description=None,
                topics=tuple(repo.components.keys()),
            )
            repos.append(metadata)
            aliases[repo_id] = metadata
            aliases[repo_id.lower()] = metadata
            aliases[metadata.full_name.lower()] = metadata
            for alias in repo.aliases or []:
                aliases[alias.lower()] = metadata
        payload = {"items": repos, "aliases": aliases}
        self.repo_cache.set(self.REPO_CACHE_KEY, payload)
        return payload

