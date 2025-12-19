"""
GitHub ingestion pipeline for the activity graph/vector index.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import time

from ..graph import GraphIngestor, GraphService
from ..graph.universal_nodes import UniversalNodeWriter
from ..vector import ContextChunk, get_vector_search_service
from ..vector.context_chunk import (
    generate_commit_entity_id,
    generate_issue_entity_id,
    generate_pr_entity_id,
)
from ..services.github_pr_service import GitHubAPIError, GitHubPRService
from ..settings.git import resolve_repo_branch
from ..utils.component_ids import normalize_component_ids
from .loggers import SignalLogWriter
from .state import ActivityIngestState

logger = logging.getLogger(__name__)


class GitActivityIngestor:
    """
    Pulls GitHub PR/commit activity and populates the graph/vector index.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        graph_service: Optional[GraphService] = None,
        vector_service=None,
    ):
        self._config = config
        activity_cfg = config.get("activity_ingest", {})
        self.git_cfg = activity_cfg.get("git") or {}
        self.enabled = bool(self.git_cfg.get("enabled", False))
        self.lookback_hours = self.git_cfg.get("lookback_hours", 168)
        self.comments_enabled = bool(self.git_cfg.get("comments_enabled", False))
        self.state_store = ActivityIngestState(activity_cfg.get("state_dir", "data/state/activity_ingest"))

        self.graph_service = graph_service or GraphService(config)
        self.graph_ingestor = GraphIngestor(self.graph_service)
        self.universal_writer = UniversalNodeWriter(self.graph_service)
        self.vector_service = vector_service or get_vector_search_service(config)
        self.vector_collection = getattr(self.vector_service, "collection", None) if self.vector_service else None
        ag_cfg = config.get("activity_graph") or {}
        slash_git_cfg = config.get("slash_git") or {}
        git_log_path = ag_cfg.get("git_graph_path") or slash_git_cfg.get("graph_log_path") or "data/logs/slash/git_graph.jsonl"
        self.git_log_writer = SignalLogWriter(git_log_path)

        self.github_cfg = config.get("github", {}) or {}
        self.default_components = self.git_cfg.get("default_components", [])
        self.default_issue_components = self.git_cfg.get("default_issue_components", self.default_components)
        self.include_issues = bool(self.git_cfg.get("include_issues", False))
        self.max_issues = self.git_cfg.get("max_issues", 15)
        self.issue_labels = self.git_cfg.get("issue_labels", [])
        self.issue_component_map = self.git_cfg.get("issue_component_map", [])
        self.issue_dissatisfaction_labels = {
            label.lower() for label in self.git_cfg.get("issue_dissatisfaction_labels", ["bug", "docs", "documentation"])
        }
        self.default_branch = (
            self.git_cfg.get("default_branch")
            or self.github_cfg.get("base_branch")
            or "main"
        )
        self.repos = self.git_cfg.get("repos", [])

    def ingest(self) -> Dict[str, Any]:
        if not self.enabled:
            logger.info("[GIT INGEST] Git ingestion disabled via config.")
            return {"prs": 0, "commits": 0, "issues": 0}

        total_prs = 0
        total_commits = 0
        total_issues = 0
        for repo_cfg in self.repos:
            try:
                repo_result = self._ingest_repo(repo_cfg)
                total_prs += repo_result.get("prs", 0)
                total_commits += repo_result.get("commits", 0)
                total_issues += repo_result.get("issues", 0)
            except GitHubAPIError as exc:
                logger.error("[GIT INGEST] GitHub API error for repo %s/%s: %s",
                             repo_cfg.get("owner"), repo_cfg.get("name"), exc)
            except Exception:
                logger.exception("[GIT INGEST] Unexpected error for repo %s/%s",
                                 repo_cfg.get("owner"), repo_cfg.get("name"))

        logger.info("[GIT INGEST] Completed ingestion (PRs=%s, commits=%s, issues=%s)", total_prs, total_commits, total_issues)
        return {"prs": total_prs, "commits": total_commits, "issues": total_issues}

    def close(self) -> None:
        if self.graph_service:
            self.graph_service.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ingest_repo(self, repo_cfg: Dict[str, Any]) -> Dict[str, int]:
        owner = repo_cfg.get("owner")
        name = repo_cfg.get("name")
        if not owner or not name:
            logger.warning("[GIT INGEST] Skipping repo without owner/name: %s", repo_cfg)
            return {"prs": 0, "commits": 0, "issues": 0}

        project_id = repo_cfg.get("project_id")

        repo_identifier = None
        if owner and name:
            repo_identifier = f"{owner}/{name}"
        elif repo_cfg.get("repo"):
            repo_identifier = repo_cfg.get("repo")
        repo_key = f"{owner}_{name}"
        state = self.state_store.load(f"git_{repo_key}")
        last_pr_updated = state.get("last_pr_updated")
        last_commit_iso = state.get("last_commit_iso")

        resolved_branch = None
        if repo_identifier:
            resolved_branch = resolve_repo_branch(
                repo_identifier,
                project_id=project_id,
                fallback_branch=self.default_branch,
            )
        branch_name = repo_cfg.get("branch") or resolved_branch or self.default_branch

        service = GitHubPRService(
            config=self._config,
            token=repo_cfg.get("token") or self.git_cfg.get("token") or self.github_cfg.get("token"),
            owner=owner,
            repo=name,
            base_branch=branch_name,
        )

        repo_result = {"prs": 0, "commits": 0, "issues": 0}
        state_updates: Dict[str, Any] = {}

        repo_identifier = f"{service.owner}/{service.repo}"

        if repo_cfg.get("include_prs", True):
            prs_ingested, newest_pr_time = self._ingest_pull_requests(
                service,
                repo_cfg,
                last_pr_updated,
                repo_identifier,
                project_id,
            )
            repo_result["prs"] = prs_ingested
            if newest_pr_time:
                state_updates["last_pr_updated"] = newest_pr_time

        if repo_cfg.get("include_commits", True):
            commits_ingested, newest_commit_time = self._ingest_commits(
                service,
                repo_cfg,
                last_commit_iso,
                repo_identifier,
                project_id,
                branch_name,
            )
            repo_result["commits"] = commits_ingested
            if newest_commit_time:
                state_updates["last_commit_iso"] = newest_commit_time

        if repo_cfg.get("include_issues", self.include_issues):
            issues_ingested, newest_issue_time = self._ingest_issues(
                service,
                repo_cfg,
                state.get("last_issue_iso"),
                repo_identifier,
                project_id,
            )
            repo_result["issues"] = issues_ingested
            if newest_issue_time:
                state_updates["last_issue_iso"] = newest_issue_time

        if state_updates:
            self.state_store.save(f"git_{repo_key}", {**state, **state_updates})

        logger.info(
            "[GIT INGEST] Repo %s/%s ingested %s PRs, %s commits, %s issues",
            owner,
            name,
            repo_result["prs"],
            repo_result["commits"],
            repo_result["issues"],
        )

        return repo_result

    def ingest_fixtures(
        self,
        fixtures: Dict[str, Any],
        repo_identifier: str = "fixtures:activity",
    ) -> Dict[str, int]:
        """
        Ingest synthetic commits/PRs from a fixture dictionary.
        """
        repo_cfg = self._get_fixture_repo_cfg()
        if not repo_cfg:
            logger.warning("[GIT INGEST] No git repo config available for fixture ingestion")
            return {"prs": 0, "commits": 0, "issues": 0}
        project_id = repo_cfg.get("project_id")

        prs = fixtures.get("pull_requests") or []
        commits = fixtures.get("commits") or []
        issues = fixtures.get("issues") or []

        pr_count = 0
        commit_count = 0
        issue_count = 0
        vector_chunks: List[ContextChunk] = []

        for pr in prs:
            files = pr.get("files", []) or []
            components, endpoint_ids, artifact_paths = self._resolve_artifacts(files, repo_cfg)
            self._upsert_artifacts(repo_identifier, artifact_paths, components)

            pr_id = pr.get("id") or f"pr:{pr.get('number')}"
            self.graph_ingestor.upsert_pr(
                pr_id=pr_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "author": pr.get("author"),
                    "repo": repo_identifier,
                    "url": pr.get("url"),
                },
            )

            signal_id = f"signal:fixture:pr:{pr.get('number')}"
            self.graph_ingestor.upsert_activity_signal(
                signal_id=signal_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "fixture_pr",
                    "repo": repo_identifier,
                    "number": pr.get("number"),
                },
                signal_weight=self._compute_pr_weight({"files": files, "total_files": len(files)}),
                last_seen=pr.get("merged_at"),
            )
            self._log_git_event(
                component_ids=components,
                event_type="pr",
                repo_identifier=repo_identifier,
                timestamp=pr.get("merged_at"),
                metadata={"number": pr.get("number"), "source": "fixture_pr"},
            )

            chunk = self._build_pr_chunk(
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "author": pr.get("author"),
                    "updated_at": pr.get("merged_at"),
                    "created_at": pr.get("merged_at"),
                    "body": pr.get("description", ""),
                    "repo": repo_identifier,
                    "url": pr.get("url"),
                },
                {"files": files},
                components,
                repo_identifier,
                project_id,
            )
            vector_chunks.append(chunk)
            pr_count += 1

        for commit in commits:
            files = commit.get("files", []) or []
            components, endpoint_ids, artifact_paths = self._resolve_artifacts(files, repo_cfg)
            self._upsert_artifacts(repo_identifier, artifact_paths, components)

            signal_id = f"signal:fixture:commit:{commit.get('sha')}"
            self.graph_ingestor.upsert_activity_signal(
                signal_id=signal_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "fixture_commit",
                    "repo": repo_identifier,
                    "sha": commit.get("sha"),
                },
                signal_weight=self._compute_commit_weight(files),
                last_seen=commit.get("date"),
            )
            self._log_git_event(
                component_ids=components,
                event_type="commit",
                repo_identifier=repo_identifier,
                timestamp=commit.get("date"),
                metadata={"sha": commit.get("sha"), "source": "fixture_commit"},
            )

            chunk = self._build_commit_chunk(
                {
                    "sha": commit.get("sha"),
                    "message": commit.get("message"),
                    "author": commit.get("author"),
                    "date": commit.get("date"),
                    "files": files,
                },
                components,
                repo_identifier,
                project_id,
                None,
            )
            vector_chunks.append(chunk)
            commit_count += 1

        for issue in issues:
            normalized_issue = {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "body": issue.get("body", ""),
                "state": issue.get("state", "open"),
                "labels": [{"name": label} for label in issue.get("labels", [])],
                "comments": issue.get("comments", 0),
                "reactions": {"total_count": issue.get("reactions", 0)},
                "updated_at": issue.get("updated_at"),
                "created_at": issue.get("created_at"),
                "url": issue.get("url"),
                "author": issue.get("author", "fixture"),
            }
            components, endpoint_ids = self._resolve_issue_scope(normalized_issue, repo_cfg)
            support_weight = self._compute_issue_weight(normalized_issue)
            issue_id = generate_issue_entity_id(normalized_issue.get("number") or 0)

            self.graph_ingestor.upsert_issue(
                issue_id=issue_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "title": normalized_issue.get("title"),
                    "state": normalized_issue.get("state"),
                    "url": normalized_issue.get("url"),
                },
            )
            self.graph_ingestor.upsert_support_case(
                case_id=f"support:{repo_identifier}:{normalized_issue.get('number')}",
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "fixture_issue",
                    "repo": repo_identifier,
                    "number": normalized_issue.get("number"),
                },
                sentiment_weight=support_weight,
                last_seen=normalized_issue.get("updated_at"),
            )

            chunk = self._build_issue_chunk(normalized_issue, components, repo_identifier, project_id)
            vector_chunks.append(chunk)
            issue_count += 1

        if vector_chunks:
            self._index_chunks(vector_chunks)

        logger.info(
            "[GIT INGEST] Fixture ingestion complete (prs=%s commits=%s issues=%s)",
            pr_count,
            commit_count,
            issue_count,
        )
        return {"prs": pr_count, "commits": commit_count, "issues": issue_count}

    def _ingest_pull_requests(
        self,
        service: GitHubPRService,
        repo_cfg: Dict[str, Any],
        last_pr_updated: Optional[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> Tuple[int, Optional[str]]:
        max_prs = repo_cfg.get("max_prs", 10)
        branch = repo_cfg.get("branch")
        prs = service.list_prs(state="all", base_branch=branch, limit=max_prs)

        lookback_cutoff = last_pr_updated or self._default_since()
        cutoff_dt = self._parse_datetime(lookback_cutoff)
        processed = 0
        latest_time = last_pr_updated
        vector_chunks: List[ContextChunk] = []

        for pr in sorted(prs, key=lambda item: item.get("updated_at") or "", reverse=False):
            updated_at = pr.get("updated_at") or pr.get("created_at")
            updated_dt = self._parse_datetime(updated_at)
            if updated_dt and cutoff_dt and updated_dt <= cutoff_dt:
                continue

            number = pr["number"]
            pr_entity_id = generate_pr_entity_id(number, repo_identifier)
            pr_details = service.fetch_pr_details(number)
            diff_summary = service.fetch_pr_diff_summary(number)
            component_ids, endpoint_ids, artifact_paths = self._resolve_artifacts(diff_summary.get("files", []), repo_cfg)

            self._upsert_artifacts(repo_identifier, artifact_paths, component_ids)
            self._ensure_repo_component_links(repo_identifier, component_ids, project_id)
            file_paths = [
                file.get("filename")
                for file in diff_summary.get("files", [])
                if isinstance(file, dict) and file.get("filename")
            ]
            labels = [
                label.get("name")
                for label in pr_details.get("labels", [])
                if isinstance(label, dict) and label.get("name")
            ]
            repo_url = f"https://github.com/{service.owner}/{service.repo}"
            pr_url = pr_details.get("url") or pr_details.get("html_url") or f"{repo_url}/pull/{number}"
            pr_properties = {
                "title": pr_details.get("title", ""),
                "state": pr_details.get("state", ""),
                "author": pr_details.get("author", ""),
                "repo": repo_identifier,
                "url": pr_url,
                "repo_url": repo_url,
                "pr_number": number,
                "merged": bool(pr_details.get("merged_at")),
                "created_at": pr_details.get("created_at"),
                "updated_at": pr_details.get("updated_at"),
                "merged_at": pr_details.get("merged_at"),
                "labels": labels,
                "files": file_paths,
                "body": pr_details.get("body"),
            }
            if project_id:
                pr_properties["project_id"] = project_id
            self.graph_ingestor.upsert_pr(
                pr_id=pr_entity_id or f"pr:{number}",
                component_ids=component_ids,
                endpoint_ids=endpoint_ids,
                properties=pr_properties,
            )

            signal_id = f"signal:pr:{repo_identifier}:{number}"
            updated_iso = self._to_iso(updated_at)
            self.graph_ingestor.upsert_activity_signal(
                signal_id=signal_id,
                component_ids=component_ids,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "github_pr",
                    "repo": repo_identifier,
                    "number": str(number),
                    "title": pr_details.get("title"),
                    "state": pr_details.get("state"),
                    "author": pr_details.get("author"),
                    "labels": labels,
                    "files": file_paths,
                    "url": pr_url,
                    "repo_url": repo_url,
                    "merged": bool(pr_details.get("merged_at")),
                    "timestamp": updated_iso,
                },
                signal_weight=self._compute_pr_weight(diff_summary),
                last_seen=updated_iso,
            )
            self._log_git_event(
                component_ids=component_ids,
                event_type="pr",
                repo_identifier=repo_identifier,
                timestamp=updated_iso,
                metadata={"number": str(number), "source": "github_pr"},
            )

            chunk = self._build_pr_chunk(
                pr_details,
                diff_summary,
                component_ids,
                repo_identifier,
                project_id,
            )
            vector_chunks.append(chunk)
            if self.comments_enabled:
                comment_chunks = self._ingest_pr_comments(
                    service=service,
                    pr_number=number,
                    pr_entity_id=pr_entity_id,
                    component_ids=component_ids,
                    repo_identifier=repo_identifier,
                    project_id=project_id,
                )
                vector_chunks.extend(comment_chunks)
            processed += 1
            latest_time = max(latest_time or "", updated_at)

        if vector_chunks:
            self._index_chunks(vector_chunks)

        return processed, latest_time

    def _ingest_commits(
        self,
        service: GitHubPRService,
        repo_cfg: Dict[str, Any],
        last_commit_iso: Optional[str],
        repo_identifier: str,
        project_id: Optional[str],
        branch_name: Optional[str],
    ) -> Tuple[int, Optional[str]]:
        max_commits = repo_cfg.get("max_commits", 20)
        since = last_commit_iso or self._default_since()
        commits = service.list_commits(branch=branch_name, since=since, per_page=max_commits, include_files=True)
        commits.sort(key=lambda item: item.get("date") or "")

        processed = 0
        latest_time = last_commit_iso
        vector_chunks: List[ContextChunk] = []

        for commit in commits:
            commit_date = commit.get("date")
            if not commit_date:
                continue
            if last_commit_iso and commit_date <= last_commit_iso:
                continue

            files = commit.get("files", []) or []
            component_ids, endpoint_ids, artifact_paths = self._resolve_artifacts(files, repo_cfg)
            self._upsert_artifacts(repo_identifier, artifact_paths, component_ids)
            self._ensure_repo_component_links(repo_identifier, component_ids, project_id)

            files_changed = [
                file.get("filename")
                for file in files
                if isinstance(file, dict) and file.get("filename")
            ]
            repo_url = f"https://github.com/{service.owner}/{service.repo}"
            commit_url = commit.get("url") or commit.get("html_url") or f"{repo_url}/commit/{commit['sha']}"
            signal_id = f"signal:commit:{repo_identifier}:{commit['sha']}"
            commit_iso = self._to_iso(commit_date)
            signal_properties = {
                "source": "github_commit",
                "repo": repo_identifier,
                "sha": commit["sha"],
                "author": commit.get("author"),
                "message": commit.get("message"),
                "text_for_embedding": commit.get("message"),
                "files": files_changed,
                "url": commit_url,
                "repo_url": repo_url,
                "timestamp": commit_iso,
            }
            if branch_name:
                signal_properties["branch"] = branch_name
            self.graph_ingestor.upsert_activity_signal(
                signal_id=signal_id,
                component_ids=component_ids,
                endpoint_ids=endpoint_ids,
                properties=signal_properties,
                signal_weight=self._compute_commit_weight(files),
                last_seen=commit_iso,
            )
            self._log_git_event(
                component_ids=component_ids,
                event_type="commit",
                repo_identifier=repo_identifier,
                timestamp=commit_iso,
                metadata={"sha": commit["sha"], "source": "github_commit"},
            )

            chunk = self._build_commit_chunk(
                commit,
                component_ids,
                repo_identifier,
                project_id,
                branch_name,
            )
            vector_chunks.append(chunk)
            processed += 1
            latest_time = commit_date

        if vector_chunks:
            self._index_chunks(vector_chunks)

        return processed, latest_time

    def _ingest_issues(
        self,
        service: GitHubPRService,
        repo_cfg: Dict[str, Any],
        last_issue_iso: Optional[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> Tuple[int, Optional[str]]:
        max_issues = repo_cfg.get("max_issues", self.max_issues)
        labels = repo_cfg.get("issue_labels", self.issue_labels)
        include_prs = repo_cfg.get("issues_include_pull_requests", False)
        since = last_issue_iso or self._default_since()

        issues = service.list_issues(
            state=repo_cfg.get("issue_state", "all"),
            labels=labels,
            since=since,
            limit=max_issues,
            include_pull_requests=include_prs,
        )
        issues.sort(key=lambda item: item.get("updated_at") or "")

        processed = 0
        latest_time = last_issue_iso
        vector_chunks: List[ContextChunk] = []

        for issue in issues:
            updated_at = issue.get("updated_at") or issue.get("created_at")
            if not updated_at:
                continue
            if last_issue_iso and updated_at <= last_issue_iso:
                continue

            components, endpoint_ids = self._resolve_issue_scope(issue, repo_cfg)
            support_weight = self._compute_issue_weight(issue)

            issue_number = issue.get("number")
            issue_id = generate_issue_entity_id(issue_number or 0, repo_identifier)
            self._ensure_repo_component_links(repo_identifier, components, project_id)
            self.graph_ingestor.upsert_issue(
                issue_id=issue_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                doc_ids=[],
                properties={
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "url": issue.get("url"),
                    "repo": repo_identifier,
                    "project_id": project_id,
                },
            )
            self.graph_ingestor.upsert_support_case(
                case_id=f"support:{repo_identifier}:{issue.get('number')}",
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "github_issue",
                    "repo": repo_identifier,
                    "number": str(issue.get("number")),
                },
                sentiment_weight=support_weight,
                last_seen=self._to_iso(updated_at),
            )

            chunk = self._build_issue_chunk(issue, components, repo_identifier, project_id)
            vector_chunks.append(chunk)
            if self.comments_enabled and issue_number:
                comment_chunks = self._ingest_issue_comments(
                    service=service,
                    issue_number=issue_number,
                    issue_entity_id=issue_id,
                    component_ids=components,
                    repo_identifier=repo_identifier,
                    project_id=project_id,
                )
                vector_chunks.extend(comment_chunks)
            processed += 1
            latest_time = updated_at

        if vector_chunks:
            self._index_chunks(vector_chunks)

        return processed, latest_time

    def _log_git_event(
        self,
        *,
        component_ids: List[str],
        event_type: str,
        repo_identifier: str,
        timestamp: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not component_ids:
            return
        ts_iso = timestamp or datetime.now(timezone.utc).isoformat()
        record = {
            "source": "git",
            "event_type": event_type,
            "timestamp": ts_iso,
            "repo": repo_identifier,
            "component_ids": component_ids,
            "properties": metadata or {},
        }
        self.git_log_writer.write(record)

    def _ingest_pr_comments(
        self,
        service: GitHubPRService,
        pr_number: int,
        pr_entity_id: Optional[str],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> List[ContextChunk]:
        review_comments = service.list_review_comments(pr_number)
        chunks: List[ContextChunk] = []
        if not review_comments:
            return chunks
        for comment in review_comments:
            chunk = self._build_pr_comment_chunk(
                pr_number=pr_number,
                pr_entity_id=pr_entity_id,
                comment=comment,
                component_ids=component_ids,
                repo_identifier=repo_identifier,
                project_id=project_id,
            )
            if not chunk:
                continue
            chunks.append(chunk)
            self._upsert_comment_event(
                event_id=chunk.entity_id,
                component_ids=component_ids,
                repo_identifier=repo_identifier,
                project_id=project_id,
                kind="review_comment",
                parent_pr_id=pr_entity_id,
            )
        return chunks

    def _ingest_issue_comments(
        self,
        service: GitHubPRService,
        issue_number: int,
        issue_entity_id: Optional[str],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> List[ContextChunk]:
        comments = service.list_issue_comments(issue_number)
        chunks: List[ContextChunk] = []
        if not comments:
            return chunks
        for comment in comments:
            chunk = self._build_issue_comment_chunk(
                issue_number=issue_number,
                issue_entity_id=issue_entity_id,
                comment=comment,
                component_ids=component_ids,
                repo_identifier=repo_identifier,
                project_id=project_id,
            )
            if not chunk:
                continue
            chunks.append(chunk)
            self._upsert_comment_event(
                event_id=chunk.entity_id,
                component_ids=component_ids,
                repo_identifier=repo_identifier,
                project_id=project_id,
                kind="issue_comment",
                parent_issue_id=issue_entity_id,
            )
        return chunks

    def _resolve_artifacts(
        self,
        files: Sequence[Dict[str, Any]],
        repo_cfg: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        component_map = repo_cfg.get("component_map", [])
        default_components = repo_cfg.get("default_components", self.default_components)

        components: List[str] = []
        endpoint_ids: List[str] = []
        artifact_ids: List[str] = []

        for file_info in files:
            path = file_info.get("filename")
            if not path:
                continue

            matched_components = []
            matched_endpoints = []
            for rule in component_map:
                matcher = rule.get("match")
                if matcher and path.startswith(matcher):
                    matched_components.extend(rule.get("components", []))
                    matched_endpoints.extend(rule.get("endpoint_ids", []))

            if not matched_components:
                matched_components.extend(default_components)

            components.extend(matched_components)
            endpoint_ids.extend(matched_endpoints)
            artifact_ids.append(path)

        components = normalize_component_ids(components)
        endpoint_ids = sorted({endpoint for endpoint in endpoint_ids if endpoint})
        artifact_ids = sorted({artifact for artifact in artifact_ids if artifact})

        return components, endpoint_ids, artifact_ids

    def _resolve_issue_scope(
        self,
        issue: Dict[str, Any],
        repo_cfg: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        issue_map = repo_cfg.get("issue_component_map") or self.issue_component_map
        labels = {
            (label or {}).get("name", "").lower()
            for label in issue.get("labels", []) or []
            if label
        }
        text_blob = f"{issue.get('title', '')} {issue.get('body', '')}".lower()

        components: List[str] = []
        endpoint_ids: List[str] = []

        for rule in issue_map:
            rule_labels = {label.lower() for label in rule.get("labels", []) if label}
            keywords = [kw.lower() for kw in rule.get("keywords", []) if kw]

            label_match = not rule_labels or bool(rule_labels & labels)
            keyword_match = not keywords or any(keyword in text_blob for keyword in keywords)
            if not (label_match and keyword_match):
                continue

            components.extend(rule.get("components", []))
            endpoint_ids.extend(rule.get("endpoint_ids", []))

        if not components:
            fallback = repo_cfg.get("default_issue_components") or self.default_issue_components
            components.extend(fallback)

        components = normalize_component_ids(components)
        endpoint_ids = sorted({endpoint for endpoint in endpoint_ids if endpoint})
        return components, endpoint_ids

    def _upsert_artifacts(self, repo_identifier: str, artifact_paths: Iterable[str], component_ids: List[str]) -> None:
        if not self.graph_ingestor.available():
            return
        for path in artifact_paths:
            artifact_id = f"code:{repo_identifier}:{path}"
            self.graph_ingestor.upsert_code_artifact(
                artifact_id=artifact_id,
                component_ids=component_ids,
                depends_on_ids=[],
                properties={"path": path, "repo": repo_identifier},
            )

    def _build_pr_chunk(
        self,
        pr_details: Dict[str, Any],
        diff_summary: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> ContextChunk:
        pr_number = pr_details.get("number")
        updated_at = self._parse_datetime(pr_details.get("updated_at") or pr_details.get("created_at"))
        body = pr_details.get("body", "") or ""
        if len(body) > 800:
            body = body[:800] + "..."

        files_changed = diff_summary.get("files", [])
        file_lines = [
            f"- {file_info.get('filename')} ({file_info.get('status')}, +{file_info.get('additions', 0)} / -{file_info.get('deletions', 0)})"
            for file_info in files_changed[:10]
        ]

        text_parts = [
            f"PR #{pr_number}: {pr_details.get('title', '')}",
            f"State: {pr_details.get('state', 'open')} | Author: {pr_details.get('author', 'unknown')}",
        ]
        if file_lines:
            text_parts.append("Changed files:")
            text_parts.extend(file_lines)
        if body:
            text_parts.append("\nDescription:\n" + body)
        chunk_text = "\n".join(text_parts)

        entity_id = generate_pr_entity_id(pr_number, repo_identifier) if pr_number else None
        chunk_entity_id = entity_id or ContextChunk.generate_chunk_id()
        metadata = {
            "url": pr_details.get("url"),
            "repo": repo_identifier,
            "repo_slug": repo_identifier,
            "kind": "pull_request",
            "components": component_ids,
            "author": pr_details.get("author"),
            "state": pr_details.get("state"),
            "branch_base": pr_details.get("base_branch"),
            "branch_head": pr_details.get("head_branch"),
            "pr_number": pr_number,
        }
        if project_id:
            metadata["project_id"] = project_id
        metadata["source_modality"] = "git"
        metadata["source_id"] = chunk_entity_id
        metadata["graph_node_id"] = chunk_entity_id

        chunk = ContextChunk(
            chunk_id=chunk_entity_id,
            entity_id=chunk_entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=f"{pr_details.get('base_branch', '')}".strip() or None,
            timestamp=updated_at,
            tags=["github", "pr"],
            metadata=metadata,
            collection=self.vector_collection,
        )
        return chunk

    def _build_commit_chunk(
        self,
        commit: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
        branch_name: Optional[str],
    ) -> ContextChunk:
        sha = commit.get("sha", "")
        timestamp = self._parse_datetime(commit.get("date"))
        files = commit.get("files", []) or []
        file_lines = [
            f"- {file_info.get('filename')} ({file_info.get('status')}, +{file_info.get('additions', 0)} / -{file_info.get('deletions', 0)})"
            for file_info in files[:10]
        ]
        text_parts = [
            f"Commit {sha} by {commit.get('author', 'unknown')}",
            "",
            commit.get("message", "").strip(),
        ]
        if file_lines:
            text_parts.extend(["", "Files touched:"])
            text_parts.extend(file_lines)
        chunk_text = "\n".join(text_parts)

        entity_id = generate_commit_entity_id(commit.get("sha", ""))
        chunk = ContextChunk(
            chunk_id=entity_id,
            entity_id=entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=None,
            timestamp=timestamp,
            tags=["github", "commit"],
            metadata=self._commit_metadata(commit, repo_identifier, project_id, branch_name, component_ids, entity_id),
            collection=self.vector_collection,
        )
        return chunk

    def _build_issue_chunk(
        self,
        issue: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> ContextChunk:
        number = issue.get("number")
        labels = [label.get("name") for label in issue.get("labels", []) if label and label.get("name")]
        updated_at = self._parse_datetime(issue.get("updated_at") or issue.get("created_at"))
        summary_lines = [
            f"Issue #{number}: {issue.get('title', '')}",
            f"State: {issue.get('state', 'open')} | Author: {issue.get('author', 'unknown')}",
        ]
        if labels:
            summary_lines.append(f"Labels: {', '.join(labels)}")
        comments = issue.get("comments", 0)
        if comments:
            summary_lines.append(f"Comments: {comments}")
        body = (issue.get("body") or "").strip()
        if body:
            summary_lines.append("")
            snippet = body[:800]
            if len(body) > 800:
                snippet += "..."
            summary_lines.append(snippet)

        chunk_text = "\n".join(summary_lines)
        entity_id = generate_issue_entity_id(number, repo_identifier) if number is not None else None
        chunk_entity_id = entity_id or ContextChunk.generate_chunk_id()
        metadata = {
            "url": issue.get("url"),
            "repo": repo_identifier,
            "repo_slug": repo_identifier,
            "state": issue.get("state"),
            "labels": labels,
            "components": component_ids,
            "kind": "issue",
            "issue_number": number,
        }
        if project_id:
            metadata["project_id"] = project_id
        metadata["source_modality"] = "git"
        metadata["source_id"] = chunk_entity_id
        metadata["graph_node_id"] = chunk_entity_id

        chunk = ContextChunk(
            chunk_id=chunk_entity_id,
            entity_id=chunk_entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=repo_identifier,
            timestamp=updated_at,
            tags=["github", "issue"],
            metadata=metadata,
            collection=self.vector_collection,
        )
        return chunk

    def _build_pr_comment_chunk(
        self,
        pr_number: int,
        pr_entity_id: Optional[str],
        comment: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> Optional[ContextChunk]:
        comment_id = comment.get("id")
        if comment_id is None:
            return None
        timestamp = self._parse_datetime(comment.get("updated_at") or comment.get("created_at"))
        author = comment.get("user")
        body = (comment.get("body") or "").strip()
        lines = [
            f"Review comment on PR #{pr_number}",
            f"Author: {author or 'unknown'}",
        ]
        if comment.get("path"):
            lines.append(f"File: {comment.get('path')}")
        if timestamp:
            lines.append(f"Timestamp: {timestamp.isoformat()}")
        if body:
            lines.extend(["", body])
        chunk_text = "\n".join(lines)
        entity_id = f"pr_comment:{repo_identifier}:{comment_id}"
        metadata = {
            "repo": repo_identifier,
            "repo_slug": repo_identifier,
            "kind": "review_comment",
            "components": component_ids,
            "comment_id": comment_id,
            "permalink": comment.get("html_url"),
            "parent_entity_id": pr_entity_id,
            "pr_number": pr_number,
            "path": comment.get("path"),
        }
        if project_id:
            metadata["project_id"] = project_id
        metadata["source_modality"] = "git"
        metadata["source_id"] = entity_id
        metadata["graph_node_id"] = entity_id

        return ContextChunk(
            chunk_id=entity_id,
            entity_id=entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=None,
            timestamp=timestamp,
            tags=["github", "review_comment"],
            metadata=metadata,
            collection=self.vector_collection,
        )

    def _build_issue_comment_chunk(
        self,
        issue_number: int,
        issue_entity_id: Optional[str],
        comment: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
    ) -> Optional[ContextChunk]:
        comment_id = comment.get("id")
        if comment_id is None:
            return None
        timestamp = self._parse_datetime(comment.get("updated_at") or comment.get("created_at"))
        author = comment.get("user")
        body = (comment.get("body") or "").strip()
        lines = [
            f"Issue comment on #{issue_number}",
            f"Author: {author or 'unknown'}",
        ]
        if timestamp:
            lines.append(f"Timestamp: {timestamp.isoformat()}")
        if body:
            lines.extend(["", body])
        chunk_text = "\n".join(lines)
        entity_id = f"issue_comment:{repo_identifier}:{comment_id}"
        metadata = {
            "repo": repo_identifier,
            "repo_slug": repo_identifier,
            "kind": "issue_comment",
            "components": component_ids,
            "comment_id": comment_id,
            "permalink": comment.get("html_url"),
            "parent_entity_id": issue_entity_id,
            "issue_number": issue_number,
        }
        if project_id:
            metadata["project_id"] = project_id
        metadata["source_modality"] = "git"
        metadata["source_id"] = entity_id
        metadata["graph_node_id"] = entity_id

        return ContextChunk(
            chunk_id=entity_id,
            entity_id=entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=None,
            timestamp=timestamp,
            tags=["github", "issue_comment"],
            metadata=metadata,
            collection=self.vector_collection,
        )

    def _upsert_comment_event(
        self,
        event_id: Optional[str],
        component_ids: List[str],
        repo_identifier: str,
        project_id: Optional[str],
        kind: str,
        parent_pr_id: Optional[str] = None,
        parent_issue_id: Optional[str] = None,
    ) -> None:
        if not event_id or not self.graph_ingestor.available():
            return
        properties = {
            "kind": kind,
            "repo": repo_identifier,
        }
        if project_id:
            properties["project_id"] = project_id
        self.graph_ingestor.upsert_git_event(
            event_id,
            component_ids=component_ids,
            properties=properties,
        )
        if parent_pr_id:
            self.graph_ingestor.link_git_event_to_pr(event_id, parent_pr_id)
        if parent_issue_id:
            self.graph_ingestor.link_git_event_to_issue(event_id, parent_issue_id)

    def _ensure_repo_component_links(self, repo_identifier: str, component_ids: List[str], project_id: Optional[str]) -> None:
        if not self.graph_ingestor.available():
            return
        repo_properties = {"project_id": project_id} if project_id else None
        self.graph_ingestor.upsert_repository(repo_identifier, repo_properties)
        for component_id in component_ids:
            self.graph_ingestor.link_repo_component(repo_identifier, component_id)

    @staticmethod
    def _commit_metadata(
        commit: Dict[str, Any],
        repo_identifier: str,
        project_id: Optional[str],
        branch_name: Optional[str],
        component_ids: List[str],
        entity_id: str,
    ) -> Dict[str, Any]:
        metadata = {
            "sha": commit.get("sha"),
            "url": commit.get("url"),
            "author": commit.get("author"),
            "repo": repo_identifier,
            "repo_slug": repo_identifier,
            "components": component_ids,
            "kind": "commit",
        }
        if project_id:
            metadata["project_id"] = project_id
        if branch_name:
            metadata["branch"] = branch_name
        metadata["source_modality"] = "git"
        metadata["source_id"] = entity_id
        metadata["graph_node_id"] = entity_id
        return metadata

    def _compute_pr_weight(self, diff_summary: Dict[str, Any]) -> float:
        total_files = diff_summary.get("total_files", 0)
        total_changes = diff_summary.get("total_additions", 0) + diff_summary.get("total_deletions", 0)
        weight = 1.0
        weight += min(total_files, 10) * 0.1
        weight += min(total_changes / 200.0, 1.0) * 0.5
        return round(weight, 4)

    def _compute_commit_weight(self, files: Sequence[Dict[str, Any]]) -> float:
        weight = 0.75
        weight += min(len(files), 10) * 0.05
        total_changes = sum((file.get("additions", 0) + file.get("deletions", 0)) for file in files)
        weight += min(total_changes / 200.0, 1.0) * 0.3
        return round(weight, 4)

    def _compute_issue_weight(self, issue: Dict[str, Any]) -> float:
        weight = 1.0
        comments = issue.get("comments", 0) or 0
        reactions = (issue.get("reactions", {}) or {}).get("total_count", 0) or 0
        labels = {
            (label or {}).get("name", "").lower()
            for label in issue.get("labels", []) or []
        }
        weight += min(comments, 20) * 0.05
        weight += min(reactions, 20) * 0.03
        if labels & self.issue_dissatisfaction_labels:
            weight += 0.4
        return round(weight, 4)

    def _index_chunks(self, chunks: List[ContextChunk]) -> None:
        if not chunks:
            logger.debug("[GIT INGEST] No vector chunks to index for this batch")
            return
        if not self.vector_service:
            logger.info(
                "[GIT INGEST] Vector service unavailable; skipped indexing %s chunks",
                len(chunks),
            )
            return
        collection = self.vector_collection or getattr(self.vector_service, "collection", "unknown")
        chunk_count = len(chunks)
        start = time.perf_counter()
        success = self.vector_service.index_chunks(chunks)
        duration_ms = (time.perf_counter() - start) * 1000
        if not success:
            logger.warning(
                "[GIT INGEST] Vector indexing failed",
                extra={
                    "collection": collection,
                    "chunk_count": chunk_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )
        else:
            logger.info(
                "[GIT INGEST] Indexed git chunks into Qdrant",
                extra={
                    "collection": collection,
                    "chunk_count": chunk_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            self.universal_writer.ingest_chunks(chunks)

    def _default_since(self) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        return cutoff.isoformat()

    @staticmethod
    def _to_iso(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return value

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _get_fixture_repo_cfg(self) -> Optional[Dict[str, Any]]:
        if self.repos:
            return self.repos[0]
        default_map = {
            "component_map": [],
            "default_components": self.default_components,
        }
        return default_map

