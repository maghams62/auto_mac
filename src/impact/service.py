"""
High-level service that wires Git/Slack inputs into the impact pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from ..config.context import ConfigContext
from ..graph import DependencyGraph, GraphService
from ..services.github_pr_service import GitHubAPIError, GitHubPRService
from ..utils.component_ids import resolve_component_id
from ..utils.slack_links import build_slack_permalink
from ..activity_graph.severity import compute_issue_severity
from .impact_analyzer import ImpactAnalyzer
from .models import (
    GitChangePayload,
    GitFileChange,
    ImpactReport,
    SlackComplaintContext,
)
from .pipeline import ImpactPipeline

logger = logging.getLogger(__name__)


@dataclass
class SlackComplaintInput:
    channel: str
    message: str
    timestamp: str
    component_ids: Optional[List[str]] = None
    api_ids: Optional[List[str]] = None
    repo: Optional[str] = None
    commit_shas: Optional[List[str]] = None
    permalink: Optional[str] = None


class GitIntegration:
    """Thin wrapper around GitHubPRService with minimal caching."""

    def __init__(self, config: Dict[str, object]):
        self.config = config
        self._clients: Dict[tuple[str, str], GitHubPRService] = {}

    def build_payload_from_pr(self, repo_full: str, pr_number: int) -> GitChangePayload:
        owner, name, repo_key = self._normalize_repo(repo_full)
        client = self._client(owner, name)
        details = client.fetch_pr_details(pr_number)
        diff = client.fetch_pr_diff_summary(pr_number)
        files = [
            GitFileChange(
                path=file_info["filename"],
                repo=repo_key,
                change_type=file_info.get("status", "modified"),
            )
            for file_info in diff.get("files", [])
        ]
        metadata = {
            "repo_full_name": f"{owner}/{name}",
            "pr_number": pr_number,
            "url": details.get("url"),
            "html_url": details.get("html_url") or details.get("url"),
            "diff_url": details.get("diff_url"),
        }
        return GitChangePayload(
            identifier=f"{repo_key}#PR-{pr_number}",
            title=details.get("title") or f"PR #{pr_number}",
            repo=repo_key,
            files=files,
            author=details.get("author"),
            description=details.get("body"),
            merged=details.get("merged", False),
            base_ref=details.get("base_branch"),
            head_ref=details.get("head_branch"),
            metadata=metadata,
        )

    def build_payload_from_commits(
        self,
        repo_full: str,
        commit_shas: Sequence[str],
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> GitChangePayload:
        owner, name, repo_key = self._normalize_repo(repo_full)
        client = self._client(owner, name)
        files: List[GitFileChange] = []
        commit_metadata: List[Dict[str, object]] = []
        for sha in commit_shas:
            commit = client.get_commit(sha, include_files=True)
            commit_metadata.append(
                {
                    "sha": sha,
                    "message": commit.get("message"),
                    "url": commit.get("url"),
                    "html_url": commit.get("html_url") or commit.get("url"),
                }
            )
            for file_info in commit.get("files", []):
                files.append(
                    GitFileChange(
                        path=file_info.get("filename", ""),
                        repo=repo_key,
                        change_type=file_info.get("status", "modified"),
                    )
                )
        identifier = f"{repo_key}@{','.join(commit_shas)}"
        metadata = {
            "repo_full_name": f"{owner}/{name}",
            "commits": commit_metadata,
            "url": (commit_metadata[0].get("url") if commit_metadata else None),
            "html_url": (commit_metadata[0].get("html_url") if commit_metadata else None),
        }
        return GitChangePayload(
            identifier=identifier,
            title=title or f"{len(commit_shas)} commit(s)",
            repo=repo_key,
            files=files,
            description=description,
            metadata=metadata,
        )

    def recent_component_changes(
        self,
        repo_full: str,
        components: Iterable[str],
        graph: DependencyGraph,
        limit: int,
        branch: Optional[str] = None,
        *,
        since: Optional[str] = None,
    ) -> List[GitChangePayload]:
        owner, name, repo_key = self._normalize_repo(repo_full)
        client = self._client(owner, name)
        commits = client.list_commits(branch=branch, per_page=limit, include_files=True, since=since)
        target_components = set(components)
        payloads: List[GitChangePayload] = []
        for commit in commits:
            sha = commit.get("sha")
            files = []
            matches: Set[str] = set()
            for file_info in commit.get("files", []):
                path = file_info.get("filename") or ""
                files.append(
                    GitFileChange(
                        path=path,
                        repo=repo_key,
                        change_type=file_info.get("status", "modified"),
                    )
                )
                matched = graph.components_for_file(repo_key, path)
                matches.update(matched & target_components)
            if not matches:
                continue
            message = commit.get("message") or ""
            metadata = {
                "repo_full_name": f"{owner}/{name}",
                "commit_sha": sha,
                "matched_components": sorted(matches),
                "url": commit.get("url"),
                "html_url": commit.get("html_url") or commit.get("url"),
                "committed_at": commit.get("date"),
            }
            payloads.append(
                GitChangePayload(
                    identifier=f"{repo_key}@{sha}",
                    title=message.splitlines()[0] if message else f"Commit {sha}",
                    repo=repo_key,
                    files=files,
                    author=commit.get("author"),
                    description=message,
                    metadata=metadata,
                )
            )
        return payloads

    def _client(self, owner: str, name: str) -> GitHubPRService:
        key = (owner, name)
        if key not in self._clients:
            self._clients[key] = GitHubPRService(self.config, owner=owner, repo=name)
        return self._clients[key]

    @staticmethod
    def _normalize_repo(repo_full: str) -> tuple[str, str, str]:
        if not repo_full or "/" not in repo_full:
            raise ValueError("repo must be of the form owner/name")
        owner, name = repo_full.split("/", 1)
        owner = owner.strip()
        name = name.strip()
        if not owner or not name:
            raise ValueError("repo must be of the form owner/name")
        return owner, name, name


class ImpactService:
    """Facade that exposes higher-level impact analysis operations."""

    def __init__(
        self,
        config_context: ConfigContext,
        *,
        graph_service: Optional[GraphService] = None,
        analyzer: Optional[ImpactAnalyzer] = None,
        pipeline: Optional[ImpactPipeline] = None,
        git_integration: Optional[GitIntegration] = None,
    ):
        self.config_context = config_context
        self.graph_service = graph_service or GraphService(config_context.data)
        self.pipeline = pipeline or ImpactPipeline(
            analyzer=analyzer,
            graph_service=self.graph_service,
            config_context=config_context,
        )
        self.analyzer = analyzer or ImpactAnalyzer(
            dependency_graph=self.pipeline.graph,
            graph_service=self.graph_service,
        )
        self.git_integration = git_integration or GitIntegration(config_context.data)
        self.settings = self.pipeline.graph.settings.impact
        self.graph = self.pipeline.graph
        self.doc_issue_service = self.pipeline.doc_issue_service
        impact_cfg = config_context.data.get("impact") or {}
        state_path_value = impact_cfg.get("auto_ingest_state_path") or "data/state/impact_auto_ingest.json"
        self._auto_ingest_state_path = Path(state_path_value) if state_path_value else None
        self._repo_configs = self._discover_git_repos()
        slack_cfg = (config_context.data.get("activity_ingest") or {}).get("slack") or {}
        slash_slack_cfg = config_context.data.get("slash_slack") or {}
        self._slack_workspace_url = (
            slack_cfg.get("workspace_url")
            or slash_slack_cfg.get("workspace_url")
            or os.getenv("SLACK_WORKSPACE_URL")
        )
        self._slack_team_id = (
            slack_cfg.get("workspace_id")
            or slash_slack_cfg.get("workspace_id")
            or slack_cfg.get("team_id")
            or slash_slack_cfg.get("team_id")
            or os.getenv("SLACK_TEAM_ID")
            or os.getenv("SLACK_WORKSPACE_ID")
        )
        self._severity_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API helpers

    def analyze_git_pr(self, repo: str, pr_number: int) -> ImpactReport:
        payload = self.git_integration.build_payload_from_pr(repo, pr_number)
        logger.info("[IMPACT] Running analysis for PR %s#%s", repo, pr_number)
        return self.pipeline.process_git_event(payload)

    def analyze_git_change(
        self,
        repo: str,
        *,
        commits: Optional[Sequence[str]] = None,
        files: Optional[List[GitFileChange]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ImpactReport:
        if not commits and not files:
            raise ValueError("commits or files must be provided")
        if commits:
            payload = self.git_integration.build_payload_from_commits(
                repo,
                commits,
                title=title,
                description=description,
            )
        else:
            repo_key = self._repo_key(repo)
            payload = GitChangePayload(
                identifier=f"{repo_key}@manual",
                title=title or "Direct file change",
                repo=repo_key,
                files=files or [],
                description=description,
                metadata={"repo_full_name": repo},
            )
        logger.info("[IMPACT] Running analysis for change %s", payload.identifier)
        return self.pipeline.process_git_event(payload)

    def analyze_slack_complaint(self, complaint: SlackComplaintInput) -> ImpactReport:
        component_ids = self._infer_components(complaint.message, complaint.component_ids)
        api_ids = self._infer_apis(complaint.message, complaint.api_ids)
        thread_id = f"slack:{complaint.channel}:{complaint.timestamp}"
        permalink = complaint.permalink or self._slack_permalink(complaint.channel, complaint.timestamp)
        slack_context = SlackComplaintContext(
            thread_id=thread_id,
            channel=complaint.channel,
            component_ids=sorted(component_ids),
            api_ids=sorted(api_ids),
            text=complaint.message,
            permalink=permalink,
        )
        recent_changes = self._collect_recent_changes(
            component_ids,
            repo_hint=complaint.repo,
            commit_shas=complaint.commit_shas,
        )
        return self.pipeline.process_slack_complaint(slack_context, recent_changes=recent_changes)

    def list_doc_issues(
        self,
        *,
        source: Optional[str] = None,
        component_id: Optional[str] = None,
        service_id: Optional[str] = None,
        repo_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return persisted DocIssues (optionally filtered) generated by impact analysis.
        """
        if not self.doc_issue_service:
            return []
        issues = self.doc_issue_service.list()

        def _matches(issue: Dict[str, Any]) -> bool:
            if source and issue.get("source") != source:
                return False
            if component_id and component_id not in issue.get("component_ids", []):
                return False
            if service_id and service_id not in issue.get("service_ids", []):
                return False
            if repo_id and issue.get("repo_id") != repo_id:
                return False
            return True

        should_filter = any([source, component_id, service_id, repo_id])
        enriched: List[Dict[str, Any]] = []
        for raw_issue in issues:
            if not isinstance(raw_issue, dict):
                continue
            if should_filter and not _matches(raw_issue):
                continue
            enriched.append(self._with_severity_metadata(raw_issue))
        return enriched

    # ------------------------------------------------------------------
    # Slack helpers

    def _infer_components(self, text: str, seeds: Optional[List[str]]) -> Set[str]:
        result: Set[str] = set()
        for seed in seeds or []:
            canonical = resolve_component_id(seed)
            if canonical:
                result.add(canonical)
        if not text:
            return result
        lower_text = text.lower()
        for component_id, metadata in self.graph.components.items():
            candidate_terms = self._component_terms(component_id, metadata)
            if any(term and term in lower_text for term in candidate_terms):
                canonical = resolve_component_id(component_id)
                if canonical:
                    result.add(canonical)
        return result

    def _infer_apis(self, text: str, seeds: Optional[List[str]]) -> Set[str]:
        result: Set[str] = set(seeds or [])
        if not text:
            return result
        lower_text = text.lower()
        for api_id, metadata in self.graph.apis.items():
            aliases = {
                api_id.lower(),
                str(metadata.get("path", "")).lower(),
                str(metadata.get("name", "")).lower(),
            }
            aliases.update(str(alias).lower() for alias in metadata.get("aliases", []) or [])
            if any(alias and alias in lower_text for alias in aliases):
                result.add(api_id)
        return result

    def _collect_recent_changes(
        self,
        component_ids: Set[str],
        *,
        repo_hint: Optional[str],
        commit_shas: Optional[Sequence[str]],
    ) -> Optional[List[GitChangePayload]]:
        if commit_shas and repo_hint:
            try:
                payload = self.git_integration.build_payload_from_commits(repo_hint, commit_shas)
                return [payload]
            except (GitHubAPIError, ValueError) as exc:
                logger.warning("[IMPACT] Failed to fetch commits for Slack context: %s", exc)

        repo_map = self.graph.component_to_repo
        repo_to_components: Dict[str, Set[str]] = {}
        normalized_components: Set[str] = set()
        for component_id in component_ids:
            canonical = resolve_component_id(component_id)
            if canonical:
                normalized_components.add(canonical)
        for component_id in normalized_components:
            repo_value = repo_hint or repo_map.get(component_id)
            if not repo_value:
                continue
            repo_to_components.setdefault(repo_value, set()).add(component_id)

        if not repo_to_components:
            return None

        payloads: List[GitChangePayload] = []
        limit = max(1, self.settings.pipeline.git_lookup_hours // 24 or 3)
        for repo_value, comps in repo_to_components.items():
            try:
                payloads.extend(
                    self.git_integration.recent_component_changes(
                        repo_value,
                        comps,
                        self.graph,
                        limit=limit,
                    )
                )
            except (GitHubAPIError, ValueError) as exc:
                logger.warning("[IMPACT] Unable to fetch recent changes for %s: %s", repo_value, exc)
        return payloads or None

    # ------------------------------------------------------------------
    # Utility helpers

    @staticmethod
    def _component_terms(component_id: str, metadata: Dict[str, object]) -> Set[str]:
        terms: Set[str] = {component_id.lower()}
        if ":" in component_id:
            terms.add(component_id.split(":", 1)[-1].lower())
        name = metadata.get("name")
        if isinstance(name, str):
            terms.add(name.lower())
        for alias in metadata.get("aliases", []) or []:
            if isinstance(alias, str):
                terms.add(alias.lower())
        return {term for term in terms if term}

    @staticmethod
    def _repo_key(repo_full: str) -> str:
        if not repo_full:
            return ""
        if "/" in repo_full:
            return repo_full.split("/", 1)[-1]
        return repo_full

    def _slack_permalink(self, channel: Optional[str], timestamp: Optional[str]) -> Optional[str]:
        return build_slack_permalink(
            channel,
            timestamp,
            workspace_url=self._slack_workspace_url,
            team_id=self._slack_team_id,
        )

    # ------------------------------------------------------------------
    # Severity helpers

    def _with_severity_metadata(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(issue)
        issue_id = issue.get("id")
        severity = self._issue_severity(issue_id)
        if severity:
            enriched["severity_score"] = severity.get("score_0_10")
            enriched["severity_score_100"] = severity.get("score")
            enriched["severity_label"] = severity.get("label")
            enriched["severity_breakdown"] = severity.get("breakdown")
            if severity.get("details"):
                enriched["severity_details"] = severity["details"]
            if severity.get("contributions"):
                enriched["severity_contributions"] = severity["contributions"]
            if severity.get("weights"):
                enriched["severity_weights"] = severity["weights"]
            if severity.get("semantic_pairs"):
                enriched["severity_semantic_pairs"] = severity["semantic_pairs"]
        return enriched

    def _issue_severity(self, issue_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not issue_id:
            return None
        cached = self._severity_cache.get(issue_id)
        if cached:
            return cached
        if not self.graph_service or not self.graph_service.is_available():
            return None
        try:
            result = compute_issue_severity(
                issue_id,
                graph_service=self.graph_service,
            )
        except ValueError:
            return None
        except Exception:
            return None
        self._severity_cache[issue_id] = result
        return result

    # ------------------------------------------------------------------
    # Health reporting

    def get_impact_health(self, *, max_events: int = 10) -> Dict[str, Any]:
        doc_issues = []
        if self.doc_issue_service:
            try:
                doc_issues = self.doc_issue_service.list()
            except Exception as exc:
                logger.warning("[IMPACT][HEALTH] Unable to read doc issues: %s", exc)
        last_issue_at = None
        repo_counts: Dict[str, int] = {}
        for issue in doc_issues:
            last_updated = issue.get("updated_at") or issue.get("detected_at")
            if last_updated and (last_issue_at is None or str(last_updated) > str(last_issue_at)):
                last_issue_at = last_updated
            repo_id = issue.get("repo_id") or "__unknown_repo__"
            repo_counts[repo_id] = repo_counts.get(repo_id, 0) + 1
        top_repos = [
            {"repo_id": repo_id, "open_doc_issues": count}
            for repo_id, count in sorted(repo_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
        events = self._recent_impact_events(limit=max_events)
        repo_health = self._build_repo_health(repo_counts)
        return {
            "data_mode": getattr(self.pipeline, "data_mode", "live"),
            "doc_issues": {
                "count": len(doc_issues),
                "last_updated_at": last_issue_at,
                "top_repos": top_repos,
            },
            "repos": repo_health,
            "recent_events": events,
        }

    def _recent_impact_events(self, *, limit: int) -> List[Dict[str, Any]]:
        log_path = getattr(self.pipeline.impact_graph_writer, "log_path", None)
        if not log_path or not log_path.exists():
            return []
        events: List[Dict[str, Any]] = []
        try:
            lines = log_path.read_text().splitlines()
        except Exception as exc:
            logger.warning("[IMPACT][HEALTH] Failed to read impact log: %s", exc)
            return []
        for line in reversed(lines):
            if len(events) >= max(1, limit):
                break
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            props = entry.get("properties") or {}
            events.append(
                {
                    "change_id": entry.get("event_id"),
                    "recorded_at": props.get("recorded_at"),
                    "impact_level": props.get("impact_level"),
                    "component_ids": entry.get("component_ids"),
                    "doc_ids": entry.get("doc_ids"),
                }
            )
        return events

    # ------------------------------------------------------------------
    # Repo/state helpers

    def _discover_git_repos(self) -> List[Dict[str, Any]]:
        activity_cfg = self.config_context.data.get("activity_ingest") or {}
        git_cfg = activity_cfg.get("git") or {}
        repos = git_cfg.get("repos") or []
        return list(repos)

    def _load_auto_ingest_state(self) -> Dict[str, Any]:
        path = getattr(self, "_auto_ingest_state_path", None)
        if not path:
            return {}
        try:
            if not path.exists():
                return {}
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[IMPACT][HEALTH] Unable to read auto-ingest state %s: %s", path, exc)
            return {}

    def _build_repo_health(self, repo_counts: Dict[str, int]) -> List[Dict[str, Any]]:
        state = self._load_auto_ingest_state()
        state_repos = state.get("repos") if isinstance(state, dict) else {}
        repos_health: List[Dict[str, Any]] = []
        for cfg in self._repo_configs:
            owner = cfg.get("owner")
            name = cfg.get("name")
            if not owner or not name:
                continue
            repo_full = f"{owner}/{name}"
            repo_key = cfg.get("repo_id") or name
            bucket = {}
            if isinstance(state_repos, dict):
                bucket = state_repos.get(repo_full, {})
            repos_health.append(
                {
                    "repo": repo_full,
                    "repo_id": repo_key,
                    "branch": cfg.get("branch"),
                    "last_run_started_at": bucket.get("last_run_started_at"),
                    "last_run_completed_at": bucket.get("last_run_completed_at"),
                    "last_success_at": bucket.get("last_success_at"),
                    "last_cursor": bucket.get("last_cursor"),
                    "doc_issues_open": repo_counts.get(repo_key, 0),
                    "last_error": bucket.get("last_error"),
                    "last_error_at": bucket.get("last_error_at"),
                }
            )
        return repos_health

