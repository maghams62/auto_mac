"""
Evidence Retrievers - Convert agent outputs to normalized Evidence format.

This module provides retriever classes that wrap existing agents
(GitAgent, SlackAgent, etc.) and convert their outputs into Evidence objects.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .evidence import Evidence, EvidenceCollection
from ..vector import VectorSearchOptions, get_vector_search_service
from ..config.qdrant import get_qdrant_collection_name
from ..vector.context_chunk import (
    generate_pr_entity_id,
    generate_slack_entity_id,
)
from ..graph import GraphAnalyticsService, GraphService
from ..slash_git.data_source import GraphGitDataSource
from ..slash_git.planner import GitQueryPlanner
from ..slash_git.models import GitTargetComponent, GitTargetRepo, TimeWindow
from ..impact.doc_issues import DocIssueService
from ..utils.git_urls import (
    determine_repo_owner_override,
    rewrite_github_url,
)

logger = logging.getLogger(__name__)


def _normalize_filter_value(value: Optional[Any]) -> Optional[List[str]]:
    """Normalize scalar/list filter inputs into a list of strings."""
    if value is None:
        return None

    if isinstance(value, (list, tuple, set)):
        normalized = [str(item).strip() for item in value if item]
        normalized = [item for item in normalized if item]
        return normalized or None

    value_str = str(value).strip()
    return [value_str] if value_str else None


class EvidenceRetriever(ABC):
    """
    Base class for evidence retrievers.

    Each retriever wraps a specific agent and converts its outputs
    to normalized Evidence objects.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def retrieve(self, query: str, **kwargs) -> EvidenceCollection:
        """
        Retrieve evidence based on a query.

        Args:
            query: Search query or context
            **kwargs: Additional retriever-specific parameters

        Returns:
            EvidenceCollection with normalized evidence
        """
        pass


class GitEvidenceRetriever(EvidenceRetriever):
    """
    Retriever for GitHub PR evidence backed by the Activity Graph / Neo4j cache.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.graph_data_source = GraphGitDataSource(config)
        self._planner = GitQueryPlanner(config)
        self.catalog = self._planner.catalog
        slash_git_cfg = (config.get("slash_git") or {})
        self.default_repo_id = slash_git_cfg.get("default_repo_id")
        self.repo_window_days = slash_git_cfg.get("default_time_window_days", 14)
        self.component_window_days = slash_git_cfg.get("component_time_window_days", 7)
        self.repo_owner_override = determine_repo_owner_override(config)

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        state: str = "all",
        branch: Optional[str] = None,
        use_live_api: bool = True,
    ) -> EvidenceCollection:
        """
        Retrieve PR evidence from the graph-backed Git cache.

        Args:
            query: Query context (used for collection metadata, not filtering)
            limit: Max PRs to retrieve
            state: (Unused) retained for compatibility
            branch: (Unused) retained for compatibility
            use_live_api: (Unused) retained for compatibility

        Returns:
            EvidenceCollection with PR evidence
        """
        collection = EvidenceCollection(query=query)

        if not self.graph_data_source.available():
            logger.warning("[GIT RETRIEVER] Graph data source unavailable; no git evidence returned")
            return collection

        repo, component = self._resolve_scope(query)
        if not repo:
            logger.warning("[GIT RETRIEVER] No repository configured; skipping git evidence")
            return collection

        window_days = self.component_window_days if component else self.repo_window_days
        window = self._build_time_window(window_days)

        try:
            prs = self.graph_data_source.get_prs(repo, component, window)
        except Exception as exc:  # pragma: no cover - guards against driver errors
            logger.exception("[GIT RETRIEVER] Failed to query graph-backed PRs: %s", exc)
            return collection

        if not prs:
            logger.info("[GIT RETRIEVER] No PRs found for repo=%s component=%s", repo.id, component.id if component else None)
            return collection

        for pr in prs[:limit]:
            evidence = self._pr_to_evidence(pr)
            metadata = evidence.metadata or {}
            metadata.setdefault("repo_id", repo.id)
            metadata.setdefault("repo_name", repo.name)
            if component:
                metadata.setdefault("component_id", component.id)
                metadata.setdefault("component_name", component.name)
            evidence.metadata = metadata
            collection.add(evidence)

        return collection

    def _pr_to_evidence(self, pr: Dict[str, Any]) -> Evidence:
        """
        Convert PR data to Evidence object.

        Args:
            pr: PR data from GitAgent

        Returns:
            Evidence object
        """
        pr_number = pr.get("number") or pr.get("pr_number")
        title = pr.get("title", "")
        state = pr.get("state", "unknown")
        author = pr.get("user", {}).get("login") if isinstance(pr.get("user"), dict) else pr.get("author")
        created_at = pr.get("created_at")
        updated_at = pr.get("updated_at")
        url = pr.get("html_url") or pr.get("url")
        url = rewrite_github_url(url, owner_override=self.repo_owner_override)
        base_branch = pr.get("base", {}).get("ref") if isinstance(pr.get("base"), dict) else pr.get("base_branch")
        head_branch = pr.get("head", {}).get("ref") if isinstance(pr.get("head"), dict) else pr.get("head_branch")
        merged_at = pr.get("merged_at")
        body = pr.get("body", "")

        # Build content summary
        content_parts = [f"PR #{pr_number}: {title}"]
        if body:
            # Truncate body to first 200 chars
            body_preview = body[:200] + "..." if len(body) > 200 else body
            content_parts.append(f"Description: {body_preview}")
        content_parts.append(f"State: {state}")
        if author:
            content_parts.append(f"Author: {author}")
        if base_branch:
            content_parts.append(f"Branch: {head_branch} → {base_branch}")

        content = "\n".join(content_parts)

        # Parse timestamp
        timestamp = None
        timestamp_str = updated_at or created_at
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass

        # Metadata
        metadata = {
            "pr_number": pr_number,
            "state": state,
            "author": author,
            "base_branch": base_branch,
            "head_branch": head_branch,
            "created_at": created_at,
            "updated_at": updated_at,
            "merged_at": merged_at,
            "merged": bool(merged_at),
        }

        # Generate entity_id
        entity_id = generate_pr_entity_id(pr_number) if pr_number else None

        return Evidence(
            source_type="git",
            source_name=f"PR #{pr_number}",
            content=content,
            metadata=metadata,
            timestamp=timestamp,
            url=url,
            confidence=0.95,  # Git data is highly reliable
            entity_id=entity_id,
        )

    def _resolve_scope(self, query: str) -> Tuple[Optional[GitTargetRepo], Optional[GitTargetComponent]]:
        component_hint = self._extract_token(query, "comp:")
        repo_hint = self._extract_token(query, "repo:")

        component: Optional[GitTargetComponent] = None
        if component_hint:
            component = self.catalog.get_component(component_hint)

        repo: Optional[GitTargetRepo] = None
        if component:
            repo = self.catalog.get_repo(component.repo_id)

        if not repo and repo_hint:
            repo = self.catalog.get_repo(repo_hint)

        if not repo and self.default_repo_id:
            repo = self.catalog.get_repo(self.default_repo_id)

        if not repo:
            repo = next(iter(self.catalog.repos.values()), None)

        return repo, component

    @staticmethod
    def _extract_token(query: str, prefix: str) -> Optional[str]:
        if not query:
            return None
        lowered = query.lower()
        prefix_lower = prefix.lower()
        for token in lowered.replace(",", " ").split():
            token = token.strip()
            if token.startswith(prefix_lower):
                return token[len(prefix_lower):].strip()
        return None

    def _build_time_window(self, days: Optional[int]) -> Optional[TimeWindow]:
        if not days or days <= 0:
            return None
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return TimeWindow(
            start=start,
            end=end,
            label=f"last {days}d",
            source="git_retriever",
        )


class SlackEvidenceRetriever(EvidenceRetriever):
    """
    Retriever for Slack message evidence.

    Prefers vector-based semantic search over ingested Slack chunks when
    available, and falls back to SlackAgent's live search API otherwise.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.vector_service = get_vector_search_service(config)
        vectordb_config = config.get("vectordb", {})
        self.default_top_k = vectordb_config.get("default_top_k", 12)
        self.min_score = vectordb_config.get("min_score", 0.35)

    def retrieve(
        self,
        query: str,
        channel: Optional[str] = None,
        limit: int = 20
    ) -> EvidenceCollection:
        """
        Retrieve Slack message evidence.

        Args:
            query: Search query
            channel: Optional channel ID/name filter
            limit: Max messages to retrieve

        Returns:
            EvidenceCollection with Slack evidence
        """
        collection = EvidenceCollection(query=query)

        # Preferred path: semantic search over ingested Slack chunks in VectorDB
        if self.vector_service:
            options = VectorSearchOptions(
                top_k=min(limit, self.default_top_k),
                min_score=self.min_score,
                source_types=["slack"],
            )
            try:
                chunks = self.vector_service.semantic_search(query, options)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception(f"[SLACK RETRIEVER] Vector search failed: {exc}")
            else:
                logger.info(
                    "[SLACK RETRIEVER] Retrieved %s messages from vector search for query='%s'",
                    len(chunks),
                    query,
                )
                for chunk in chunks:
                    evidence = chunk.to_evidence()
                    metadata = evidence.metadata or {}
                    metadata.setdefault("component", chunk.component)
                    metadata.setdefault("service", chunk.service)
                    metadata.setdefault("tags", chunk.tags)
                    metadata.setdefault("source", "slack")
                    if "_score" in chunk.metadata:
                        metadata["vector_score"] = chunk.metadata["_score"]
                    evidence.metadata = metadata

                    # Prefer Slack app deeplink; fall back to web permalink.
                    channel_id = (
                        metadata.get("channel_id")
                        or metadata.get("channel")
                        or chunk.metadata.get("channel_id")
                    )
                    ts = (
                        metadata.get("thread_ts")
                        or metadata.get("timestamp")
                        or metadata.get("ts")
                        or chunk.metadata.get("thread_ts")
                        or chunk.metadata.get("timestamp")
                        or chunk.metadata.get("ts")
                    )
                    if not ts and isinstance(evidence.entity_id, str) and evidence.entity_id.startswith("slack:"):
                        parts = evidence.entity_id.split(":")
                        if len(parts) >= 3:
                            ts = parts[-1]

                    team_id = (
                        metadata.get("workspace_id")
                        or os.getenv("SLACK_TEAM_ID")
                        or os.getenv("SLACK_WORKSPACE_ID")
                    )

                    deeplink_url = None
                    if channel_id and team_id:
                        base = f"slack://channel?team={team_id}&id={channel_id}"
                        ts_str = str(ts).strip() if ts is not None else ""
                        deeplink_url = f"{base}&message={ts_str}" if ts_str else base

                    if deeplink_url:
                        evidence.url = deeplink_url
                    elif not evidence.url:
                        evidence.url = (
                            metadata.get("permalink")
                            or metadata.get("url")
                            or chunk.metadata.get("permalink")
                            or chunk.metadata.get("url")
                        )

                    collection.add(evidence)

                if len(collection) > 0:
                    return collection

        # Fallback: live Slack search via SlackAgent tool
        from .slack_agent import search_slack_messages

        try:
            tool_callable = getattr(search_slack_messages, "func", search_slack_messages)
            # Search Slack using existing SlackAgent tool
            result = tool_callable(
                query=query,
                channel=channel,
                limit=limit
            )

            if result.get("error"):
                logger.error(f"[SLACK RETRIEVER] Error searching Slack: {result.get('error_message')}")
                return collection

            messages = result.get("messages", [])
            logger.info(f"[SLACK RETRIEVER] Retrieved {len(messages)} messages")

            # Convert each message to Evidence
            for msg in messages:
                evidence = self._message_to_evidence(msg)
                collection.add(evidence)

        except Exception as exc:
            logger.exception(f"[SLACK RETRIEVER] Exception during retrieval: {exc}")

        return collection

    def _message_to_evidence(self, msg: Dict[str, Any]) -> Evidence:
        """
        Convert Slack message to Evidence object.

        Args:
            msg: Message data from SlackAgent

        Returns:
            Evidence object
        """
        text = msg.get("text", "")
        user = msg.get("username") or msg.get("user", "unknown")
        timestamp_str = msg.get("ts") or msg.get("timestamp", "")
        channel_info = msg.get("channel", {})
        channel_name = channel_info.get("name") if isinstance(channel_info, dict) else str(channel_info)
        channel_id = channel_info.get("id") if isinstance(channel_info, dict) else channel_info
        permalink = msg.get("permalink")

        # Build content
        content = f"{user}: {text}"

        # Parse timestamp
        timestamp = None
        if timestamp_str:
            try:
                # Slack timestamps are unix timestamps
                timestamp = datetime.fromtimestamp(float(timestamp_str))
            except (ValueError, TypeError):
                pass

        # Metadata
        metadata = {
            "user": user,
            "channel": channel_name or "unknown",
            "thread_ts": msg.get("thread_ts"),
            "reply_count": msg.get("reply_count", 0),
        }

        # Generate entity_id
        entity_id = None
        if channel_id and timestamp_str:
            entity_id = generate_slack_entity_id(str(channel_id), str(timestamp_str))

        return Evidence(
            source_type="slack",
            source_name=f"Slack #{channel_name or 'unknown'}",
            content=content,
            metadata=metadata,
            timestamp=timestamp,
            url=permalink,
            confidence=0.75,  # Slack discussions are less authoritative than code
            entity_id=entity_id,
        )


class DocsEvidenceRetriever(EvidenceRetriever):
    """
    Retriever for documentation evidence backed by VectorDB.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        vectordb_config = config.get("vectordb", {}) or {}

        # When using Qdrant, synthetic doc pages are indexed into a dedicated
        # `{base_collection}_docs` collection via DocVectorIndexer. Point this
        # retriever at that docs-specific collection so semantic search actually
        # sees those pages instead of the generic multi-modal collection.
        base_collection = vectordb_config.get("collection")
        resolved_base = get_qdrant_collection_name(base_collection)
        docs_collection = f"{resolved_base}_docs"

        self.vector_service = get_vector_search_service(
            config,
            collection_override=docs_collection,
        )

        self.default_top_k = vectordb_config.get("default_top_k", 12)
        self.min_score = vectordb_config.get("min_score", 0.35)

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        component: Optional[str] = None,
        service: Optional[str] = None,
        tags: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceCollection:
        """
        Retrieve documentation evidence using semantic search.
        """
        collection = EvidenceCollection(query=query)

        if not self.vector_service:
            logger.info("[DOCS RETRIEVER] Vector search not configured; skipping docs evidence")
            return collection

        tag_filters = _normalize_filter_value(tags)
        options = VectorSearchOptions(
            top_k=min(limit, self.default_top_k),
            min_score=self.min_score,
            source_types=["doc"],
            components=_normalize_filter_value(component),
            services=_normalize_filter_value(service),
            tags=tag_filters,
            since=since,
            metadata_filters=metadata_filters or {},
        )

        logger.info(
            "[DOCS RETRIEVER] Query='%s' limit=%s component=%s service=%s tags=%s",
            query,
            limit,
            component,
            service,
            tags,
        )

        chunks = self.vector_service.semantic_search(query, options)
        logger.info(
            "[DOCS RETRIEVER] Retrieved %s doc chunks for query '%s'",
            len(chunks),
            query,
        )
        for chunk in chunks:
            evidence = chunk.to_evidence()
            metadata = evidence.metadata or {}
            metadata.setdefault("component", chunk.component)
            metadata.setdefault("service", chunk.service)
            metadata.setdefault("tags", chunk.tags)
            metadata.setdefault("source", "docs")
            if "_score" in chunk.metadata:
                metadata["vector_score"] = chunk.metadata["_score"]
            evidence.metadata = metadata
            collection.add(evidence)

        return collection

class IssuesEvidenceRetriever(EvidenceRetriever):
    """
    Retriever for issue tracker evidence backed by VectorDB.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.vector_service = get_vector_search_service(config)
        vectordb_config = config.get("vectordb", {})
        self.default_top_k = vectordb_config.get("default_top_k", 12)
        self.min_score = vectordb_config.get("min_score", 0.35)

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        component: Optional[str] = None,
        service: Optional[str] = None,
        tags: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceCollection:
        """
        Retrieve issue tracker evidence using semantic search.
        """
        collection = EvidenceCollection(query=query)

        if not self.vector_service:
            logger.info("[ISSUES RETRIEVER] Vector search not configured; skipping issues evidence")
            return collection

        options = VectorSearchOptions(
            top_k=min(limit, self.default_top_k),
            min_score=self.min_score,
            source_types=["issue"],
            components=_normalize_filter_value(component),
            services=_normalize_filter_value(service),
            tags=_normalize_filter_value(tags),
            since=since,
            metadata_filters=metadata_filters or {},
        )

        logger.info(
            "[ISSUES RETRIEVER] Query='%s' limit=%s component=%s service=%s tags=%s",
            query,
            limit,
            component,
            service,
            tags,
        )

        chunks = self.vector_service.semantic_search(query, options)
        logger.info(
            "[ISSUES RETRIEVER] Retrieved %s issue chunks for query '%s'",
            len(chunks),
            query,
        )
        for chunk in chunks:
            evidence = chunk.to_evidence()
            metadata = evidence.metadata or {}
            metadata.setdefault("component", chunk.component)
            metadata.setdefault("service", chunk.service)
            metadata.setdefault("tags", chunk.tags)
            metadata.setdefault("source", "issues")
            if "_score" in chunk.metadata:
                metadata["vector_score"] = chunk.metadata["_score"]
            evidence.metadata = metadata
            collection.add(evidence)

        return collection


class DocIssuesEvidenceRetriever(EvidenceRetriever):
    """
    Retriever that surfaces persisted DocIssues as evidence.
    """

    _SEVERITY_WEIGHTS = {
        "critical": 3.0,
        "high": 2.0,
        "medium": 1.2,
        "low": 0.5,
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        path_value = self._resolve_doc_issue_path(config)
        self.doc_issue_path = Path(path_value) if path_value else None
        self.doc_issue_service = DocIssueService(path=self.doc_issue_path) if self.doc_issue_path else None

    def retrieve(
        self,
        query: str,
        limit: int = 10,
    ) -> EvidenceCollection:
        collection = EvidenceCollection(query=query)
        issues = self._load_doc_issues()
        if not issues:
            return collection

        component_hint = self._extract_component_token(query)
        ranked = sorted(
            issues,
            key=lambda issue: self._score_issue(issue, query, component_hint),
            reverse=True,
        )

        for issue in ranked[: max(1, limit)]:
            metadata = {
                "severity": issue.get("severity"),
                "component_ids": issue.get("component_ids") or [],
                "service_ids": issue.get("service_ids") or [],
                "repo_id": issue.get("repo_id"),
                "doc_path": issue.get("doc_path"),
                "doc_issue_id": issue.get("id"),
                "state": issue.get("state"),
                "source": issue.get("source"),
                "score": self._score_issue(issue, query, component_hint),
            }
            url = issue.get("doc_url") or self._first_link(issue) or issue.get("doc_path")
            title = issue.get("doc_title") or issue.get("doc_path") or issue.get("id") or "Doc issue"
            content_lines = [
                issue.get("summary") or "",
                f"Severity: {issue.get('severity', 'unknown')}",
            ]
            if issue.get("component_ids"):
                content_lines.append(f"Components: {', '.join(issue['component_ids'])}")

            timestamp = self._parse_timestamp(issue.get("updated_at") or issue.get("detected_at"))
            collection.add(
                Evidence(
                    source_type="doc_issue",
                    source_name=title,
                    content="\n".join(line for line in content_lines if line),
                    metadata=metadata,
                    timestamp=timestamp,
                    url=url,
                    confidence=self._confidence(metadata["score"]),
                    entity_id=issue.get("id"),
                )
            )

        return collection

    def _load_doc_issues(self) -> List[Dict[str, Any]]:
        if not self.doc_issue_service:
            return []
        try:
            return self.doc_issue_service.list()
        except Exception:
            return []

    @staticmethod
    def _resolve_doc_issue_path(config: Dict[str, Any]) -> Optional[str]:
        search_scope = (
            ((config.get("search") or {}).get("modalities") or {}).get("doc_issues") or {}
        ).get("scope") or {}
        if search_scope.get("path"):
            return search_scope["path"]

        ag_cfg = config.get("activity_graph") or {}
        if ag_cfg.get("doc_issues_path"):
            return ag_cfg["doc_issues_path"]

        doc_ingest_cfg = (config.get("activity_ingest") or {}).get("doc_issues") or {}
        if doc_ingest_cfg.get("path"):
            return doc_ingest_cfg["path"]

        return "data/live/doc_issues.json"

    @classmethod
    def _score_issue(cls, issue: Dict[str, Any], query: str, component_hint: Optional[str]) -> float:
        severity = str(issue.get("severity") or "medium").lower()
        severity_score = cls._SEVERITY_WEIGHTS.get(severity, 1.0)

        timestamp = issue.get("updated_at") or issue.get("detected_at")
        recency_multiplier = 1.0
        if timestamp:
            parsed = cls._parse_timestamp(timestamp)
            if parsed:
                age_hours = (datetime.now(tz=parsed.tzinfo or timezone.utc) - parsed).total_seconds() / 3600.0
                if age_hours <= 24:
                    recency_multiplier = 1.0
                elif age_hours <= 24 * 7:
                    recency_multiplier = 0.7
                else:
                    recency_multiplier = 0.4

        query_bonus = 0.0
        normalized_query = (query or "").lower()
        if normalized_query:
            haystack = " ".join(
                str(issue.get(field) or "").lower()
                for field in ("summary", "doc_title", "doc_path")
            )
            if normalized_query in haystack:
                query_bonus += 0.5
        if component_hint and component_hint in (issue.get("component_ids") or []):
            query_bonus += 0.5

        return severity_score * recency_multiplier + query_bonus

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _extract_component_token(query: str) -> Optional[str]:
        if not query:
            return None
        for token in query.replace(",", " ").split():
            token = token.strip()
            if token.startswith("comp:"):
                return token
        return None

    @staticmethod
    def _first_link(issue: Dict[str, Any]) -> Optional[str]:
        links = issue.get("links") or []
        for link in links:
            if isinstance(link, dict) and link.get("url"):
                return link["url"]
        return None

    @staticmethod
    def _confidence(score: float) -> float:
        # Normalize into 0-1 range with diminishing returns
        return max(0.3, min(0.99, score / 3.0))


class ActivityAnalyticsRetriever(EvidenceRetriever):
    """
    Retriever that surfaces activity graph analytics as evidence.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.graph_service = GraphService(config)
        self.analytics = GraphAnalyticsService(self.graph_service)

    def retrieve(
        self,
        query: str,
        component: Optional[str] = None,
        mode: str = "activity",
        window_hours: int = 168,
        limit: int = 5,
        components: Optional[List[str]] = None,
    ) -> EvidenceCollection:
        collection = EvidenceCollection(query=query)

        if not self.analytics.is_available():
            logger.info("[ACTIVITY RETRIEVER] Graph analytics unavailable; skipping")
            return collection

        normalized_mode = (mode or "activity").lower()
        component = component or self._extract_component_from_text(query)

        if normalized_mode == "dissatisfaction":
            targets = components or ([component] if component else None)
            results = self.analytics.get_dissatisfaction_leaderboard(
                window_hours=window_hours,
                limit=limit,
                components=targets,
            )
            if not results:
                return collection

            content_lines = [
                f"Top dissatisfied components (window={window_hours}h):",
            ]
            for idx, entry in enumerate(results, start=1):
                content_lines.append(
                    f"{idx}. {entry['component_id']} "
                    f"(score={entry['total_score']}, support={entry['support_score']}, issues={entry['issue_count']})"
                )

            collection.add(
                Evidence(
                    source_type="activity_graph",
                    source_name="Activity Graph – Dissatisfaction",
                    content="\n".join(content_lines),
                    metadata={
                        "window_hours": window_hours,
                        "limit": limit,
                        "results": results,
                    },
                )
            )
            return collection

        if not component:
            logger.info("[ACTIVITY RETRIEVER] No component hint found; skipping activity summary")
            return collection

        result = self.analytics.get_component_activity(
            component_id=component,
            window_hours=window_hours,
            limit=limit,
        )
        signals = result.get("signals", []) or []

        content_lines = [
            f"Component {component} activity score: {result.get('activity_score', 0.0)} "
            f"(window={window_hours}h)",
        ]
        if signals:
            content_lines.append("Recent signals:")
            for signal in signals:
                content_lines.append(
                    f"- {signal.get('id')} (source={signal.get('source')}, "
                    f"weight={signal.get('weight')}, last_seen={signal.get('last_seen')})"
                )

        collection.add(
            Evidence(
                source_type="activity_graph",
                source_name=f"Activity Graph – {component}",
                content="\n".join(content_lines),
                metadata={
                    "component_id": component,
                    "window_hours": window_hours,
                    "signals": signals,
                    "activity_score": result.get("activity_score", 0.0),
                },
                entity_id=component,
            )
        )
        return collection

    @staticmethod
    def _extract_component_from_text(text: str) -> Optional[str]:
        if not text:
            return None
        for token in text.replace(",", " ").split():
            token = token.strip()
            if token.startswith("comp:"):
                return token
        return None


def get_retriever(source_type: str, config: Dict[str, Any]) -> Optional[EvidenceRetriever]:
    """
    Factory function to get retriever for a specific source type.

    Args:
        source_type: Type of source ("git", "slack", "docs", "issues")
        config: Configuration dictionary

    Returns:
        Appropriate retriever instance, or None if not available
    """
    retrievers = {
        "git": GitEvidenceRetriever,
        "slack": SlackEvidenceRetriever,
        "docs": DocsEvidenceRetriever,
        "issues": IssuesEvidenceRetriever,
        "doc_issues": DocIssuesEvidenceRetriever,
        "activity_graph": ActivityAnalyticsRetriever,
    }

    retriever_class = retrievers.get(source_type)
    if not retriever_class:
        logger.warning(f"[RETRIEVER FACTORY] Unknown source type: {source_type}")
        return None

    return retriever_class(config)
