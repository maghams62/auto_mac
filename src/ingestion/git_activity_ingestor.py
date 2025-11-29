"""
GitHub ingestion pipeline for the activity graph/vector index.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import time

from ..graph import GraphIngestor, GraphService
from ..vector import ContextChunk, get_vector_search_service
from ..vector.context_chunk import (
    generate_commit_entity_id,
    generate_issue_entity_id,
    generate_pr_entity_id,
)
from ..services.github_pr_service import GitHubAPIError, GitHubPRService
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
        self.state_store = ActivityIngestState(activity_cfg.get("state_dir", "data/state/activity_ingest"))

        self.graph_service = graph_service or GraphService(config)
        self.graph_ingestor = GraphIngestor(self.graph_service)
        self.vector_service = vector_service or get_vector_search_service(config)
        self.vector_collection = getattr(self.vector_service, "collection", None) if self.vector_service else None

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

        repo_key = f"{owner}_{name}"
        state = self.state_store.load(f"git_{repo_key}")
        last_pr_updated = state.get("last_pr_updated")
        last_commit_iso = state.get("last_commit_iso")

        service = GitHubPRService(
            config=self._config,
            token=repo_cfg.get("token") or self.git_cfg.get("token") or self.github_cfg.get("token"),
            owner=owner,
            repo=name,
            base_branch=repo_cfg.get("branch") or self.git_cfg.get("default_branch"),
        )

        repo_result = {"prs": 0, "commits": 0, "issues": 0}
        state_updates: Dict[str, Any] = {}

        repo_identifier = f"{service.owner}/{service.repo}"

        if repo_cfg.get("include_prs", True):
            prs_ingested, newest_pr_time = self._ingest_pull_requests(service, repo_cfg, last_pr_updated, repo_identifier)
            repo_result["prs"] = prs_ingested
            if newest_pr_time:
                state_updates["last_pr_updated"] = newest_pr_time

        if repo_cfg.get("include_commits", True):
            commits_ingested, newest_commit_time = self._ingest_commits(service, repo_cfg, last_commit_iso, repo_identifier)
            repo_result["commits"] = commits_ingested
            if newest_commit_time:
                state_updates["last_commit_iso"] = newest_commit_time

        if repo_cfg.get("include_issues", self.include_issues):
            issues_ingested, newest_issue_time = self._ingest_issues(
                service,
                repo_cfg,
                state.get("last_issue_iso"),
                repo_identifier,
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

            chunk = self._build_issue_chunk(normalized_issue, components, repo_identifier)
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
            pr_details = service.fetch_pr_details(number)
            diff_summary = service.fetch_pr_diff_summary(number)
            component_ids, endpoint_ids, artifact_paths = self._resolve_artifacts(diff_summary.get("files", []), repo_cfg)

            self._upsert_artifacts(repo_identifier, artifact_paths, component_ids)
            self.graph_ingestor.upsert_pr(
                pr_id=f"pr:{number}",
                component_ids=component_ids,
                endpoint_ids=endpoint_ids,
                properties={
                    "title": pr_details.get("title", ""),
                    "state": pr_details.get("state", ""),
                    "author": pr_details.get("author", ""),
                    "repo": repo_identifier,
                    "url": pr_details.get("url", ""),
                },
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
                },
                signal_weight=self._compute_pr_weight(diff_summary),
                last_seen=updated_iso,
            )

            chunk = self._build_pr_chunk(pr_details, diff_summary, component_ids, repo_identifier)
            vector_chunks.append(chunk)
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
    ) -> Tuple[int, Optional[str]]:
        max_commits = repo_cfg.get("max_commits", 20)
        branch = repo_cfg.get("branch")
        since = last_commit_iso or self._default_since()
        commits = service.list_commits(branch=branch, since=since, per_page=max_commits, include_files=True)
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

            signal_id = f"signal:commit:{repo_identifier}:{commit['sha']}"
            self.graph_ingestor.upsert_activity_signal(
                signal_id=signal_id,
                component_ids=component_ids,
                endpoint_ids=endpoint_ids,
                properties={
                    "source": "github_commit",
                    "repo": repo_identifier,
                    "sha": commit["sha"],
                },
                signal_weight=self._compute_commit_weight(files),
                last_seen=self._to_iso(commit_date),
            )

            chunk = self._build_commit_chunk(commit, component_ids, repo_identifier)
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

            issue_id = generate_issue_entity_id(issue.get("number") or 0)
            self.graph_ingestor.upsert_issue(
                issue_id=issue_id,
                component_ids=components,
                endpoint_ids=endpoint_ids,
                properties={
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "url": issue.get("url"),
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

            chunk = self._build_issue_chunk(issue, components, repo_identifier)
            vector_chunks.append(chunk)
            processed += 1
            latest_time = updated_at

        if vector_chunks:
            self._index_chunks(vector_chunks)

        return processed, latest_time

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

        components = sorted({comp for comp in components if comp})
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

        components = sorted({comp for comp in components if comp})
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

        entity_id = generate_pr_entity_id(pr_number) if pr_number else ContextChunk.generate_chunk_id()
        chunk = ContextChunk(
            chunk_id=ContextChunk.generate_chunk_id(),
            entity_id=entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=f"{pr_details.get('base_branch', '')}".strip() or None,
            timestamp=updated_at,
            tags=["github", "pr"],
            metadata={
                "url": pr_details.get("url"),
                "repo": repo_identifier,
                "author": pr_details.get("author"),
                "state": pr_details.get("state"),
            },
            collection=self.vector_collection,
        )
        return chunk

    def _build_commit_chunk(
        self,
        commit: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
    ) -> ContextChunk:
        sha = commit.get("sha", "")[:7]
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
            chunk_id=ContextChunk.generate_chunk_id(),
            entity_id=entity_id,
            source_type="git",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=None,
            timestamp=timestamp,
            tags=["github", "commit"],
            metadata={
                "sha": commit.get("sha"),
                "url": commit.get("url"),
                "author": commit.get("author"),
                "repo": repo_identifier,
            },
            collection=self.vector_collection,
        )
        return chunk

    def _build_issue_chunk(
        self,
        issue: Dict[str, Any],
        component_ids: List[str],
        repo_identifier: str,
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
        entity_id = generate_issue_entity_id(number) if number is not None else ContextChunk.generate_chunk_id()
        chunk = ContextChunk(
            chunk_id=ContextChunk.generate_chunk_id(),
            entity_id=entity_id,
            source_type="issue",
            text=chunk_text,
            component=component_ids[0] if component_ids else None,
            service=repo_identifier,
            timestamp=updated_at,
            tags=["github", "issue"],
            metadata={
                "url": issue.get("url"),
                "repo": repo_identifier,
                "state": issue.get("state"),
                "labels": labels,
            },
            collection=self.vector_collection,
        )
        return chunk

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

