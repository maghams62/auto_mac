"""
Evidence Retrievers - Convert agent outputs to normalized Evidence format.

This module provides retriever classes that wrap existing agents
(GitAgent, SlackAgent, etc.) and convert their outputs into Evidence objects.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .evidence import Evidence, EvidenceCollection
from ..vector import VectorSearchOptions, get_vector_search_service
from ..vector.context_chunk import (
    generate_pr_entity_id,
    generate_slack_entity_id,
)
from ..graph import GraphAnalyticsService, GraphService

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
    Retriever for GitHub PR evidence.

    Wraps GitAgent's list_recent_prs and get_pr_details functions.
    """

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        state: str = "all",
        branch: Optional[str] = None,
        use_live_api: bool = True
    ) -> EvidenceCollection:
        """
        Retrieve PR evidence from GitHub.

        Args:
            query: Query context (used for collection metadata, not filtering)
            limit: Max PRs to retrieve
            state: PR state filter ("open", "closed", "all")
            branch: Optional branch filter
            use_live_api: Whether to use live API or webhook cache

        Returns:
            EvidenceCollection with PR evidence
        """
        from .git_agent import list_recent_prs

        collection = EvidenceCollection(query=query)

        try:
            # Fetch PRs using existing GitAgent tool
            result = list_recent_prs(
                limit=limit,
                state=state,
                branch=branch,
                use_live_api=use_live_api
            )

            if result.get("error"):
                logger.error(f"[GIT RETRIEVER] Error fetching PRs: {result.get('error_message')}")
                return collection

            prs = result.get("prs", [])
            logger.info(f"[GIT RETRIEVER] Retrieved {len(prs)} PRs")

            # Convert each PR to Evidence
            for pr in prs:
                evidence = self._pr_to_evidence(pr)
                collection.add(evidence)

        except Exception as exc:
            logger.exception(f"[GIT RETRIEVER] Exception during retrieval: {exc}")

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


class SlackEvidenceRetriever(EvidenceRetriever):
    """
    Retriever for Slack message evidence.

    Wraps SlackAgent's search_slack_messages function.
    """

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
        from .slack_agent import search_slack_messages

        collection = EvidenceCollection(query=query)

        try:
            # Search Slack using existing SlackAgent tool
            result = search_slack_messages(
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
        "activity_graph": ActivityAnalyticsRetriever,
    }

    retriever_class = retrievers.get(source_type)
    if not retriever_class:
        logger.warning(f"[RETRIEVER FACTORY] Unknown source type: {source_type}")
        return None

    return retriever_class(config)
