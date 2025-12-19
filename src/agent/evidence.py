"""
Evidence Model - Unified representation for multi-source data.

This module provides a normalized Evidence format that abstracts over
different data sources (Git PRs, Slack messages, docs, issues, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union

from src.settings.policy import get_priority_list

logger = logging.getLogger(__name__)

_DEFAULT_PRIORITY_ORDER = ["git", "docs", "doc_issue", "activity_graph", "issues", "slack", "unknown"]

# Human-readable source descriptions
SOURCE_DESCRIPTIONS = {
    "git": "Git commit/PR",
    "docs": "Documentation",
    "doc_issue": "Doc issue",
    "activity_graph": "Activity graph analytics",
    "issues": "Issue tracker",
    "slack": "Slack discussion",
    "unknown": "Unknown source",
}


def _build_priority_map(priority_list: Optional[list]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    if priority_list:
        for idx, source in enumerate(priority_list):
            if source not in mapping:
                mapping[source] = idx + 1
    rank = len(mapping) + 1
    for source in _DEFAULT_PRIORITY_ORDER:
        if source not in mapping:
            mapping[source] = rank
            rank += 1
    return mapping


def _resolve_source_priority(source_type: str, domain: str = "api_params") -> int:
    try:
        priority_list = get_priority_list(domain)
    except Exception as exc:  # pragma: no cover - settings manager failures rare
        logger.warning("[EVIDENCE] Failed to load source priority: %s", exc)
        priority_list = None
    mapping = _build_priority_map(priority_list)
    return mapping.get(source_type, mapping.get("unknown", len(mapping) + 1))


def slack_thread_evidence_id(workspace_id: str, channel_id: str, thread_ts: str) -> str:
    """
    Canonical Slack thread identifier (config/canonical_ids.yaml > evidence_id_schemas.slack_thread).
    """
    normalized_ts = str(thread_ts).strip()
    return f"slack:{workspace_id}:{channel_id}:{normalized_ts}"


def slack_message_evidence_id(workspace_id: str, channel_id: str, message_ts: str) -> str:
    """
    Canonical Slack message identifier (evidence_id_schemas.slack_message).
    """
    normalized_ts = str(message_ts).strip()
    return f"slack:{workspace_id}:{channel_id}:{normalized_ts}"


def git_pr_evidence_id(repo: str, pr_number: Union[int, str]) -> str:
    """
    Canonical Git PR identifier (evidence_id_schemas.git_pr).
    """
    return f"git:{repo}:{pr_number}"


def git_commit_evidence_id(repo: str, sha: str) -> str:
    """
    Canonical Git commit identifier (evidence_id_schemas.git_commit).
    """
    return f"git:{repo}:{sha}"


def doc_fragment_evidence_id(repo: str, path: str, line_range: str) -> str:
    """
    Canonical documentation fragment identifier (evidence_id_schemas.doc_fragment).
    """
    normalized_range = line_range if line_range.startswith("#") else f"#{line_range}"
    return f"doc:{repo}:{path}{normalized_range}"


def ticket_evidence_id(system: str, ticket_id: Union[int, str]) -> str:
    """
    Canonical ticket identifier (evidence_id_schemas.ticket).
    """
    return f"ticket:{system}:{ticket_id}"


@dataclass
class Evidence:
    """
    Normalized evidence from a single source.

    This abstraction allows the reasoning engine to work with data
    from Git, Slack, docs, issues, and future sources in a uniform way.

    Attributes:
        source_type: Type of source ("git", "slack", "docs", "issues")
        source_name: Specific source identifier (e.g., "PR #123", "slack #general")
        content: Main content/summary of this evidence
        metadata: Additional structured data (varies by source)
        timestamp: When this evidence was created/updated
        url: Optional link to view this evidence
        confidence: Optional confidence score (0.0-1.0) for this evidence
        entity_id: Optional stable entity ID (e.g., "pr:123", "doc:payments-guide")
    """

    source_type: str
    source_name: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    url: Optional[str] = None
    confidence: Optional[float] = None
    entity_id: Optional[str] = None

    @property
    def priority(self) -> int:
        """
        Get priority level for this evidence source.

        Returns:
            Priority number (lower = higher trust)
        """
        return _resolve_source_priority(self.source_type)

    @property
    def source_description(self) -> str:
        """
        Get human-readable source description.

        Returns:
            Source description string
        """
        return SOURCE_DESCRIPTIONS.get(self.source_type, SOURCE_DESCRIPTIONS["unknown"])

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert evidence to dictionary format.

        Returns:
            Dictionary representation
        """
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "url": self.url,
            "confidence": self.confidence,
            "entity_id": self.entity_id,
            "priority": self.priority,
            "source_description": self.source_description,
        }

    def format_for_llm(self) -> str:
        """
        Format evidence for LLM consumption.

        Returns:
            Formatted string suitable for LLM prompts
        """
        lines = [
            f"SOURCE: {self.source_name} ({self.source_description})",
            f"CONTENT: {self.content}",
        ]

        if self.entity_id:
            lines.append(f"ENTITY_ID: {self.entity_id}")

        if self.timestamp:
            lines.append(f"TIMESTAMP: {self.timestamp.isoformat()}")

        if self.url:
            lines.append(f"URL: {self.url}")

        if self.confidence is not None:
            lines.append(f"CONFIDENCE: {self.confidence:.2f}")

        if self.metadata:
            # Include selected metadata fields
            metadata_lines = []
            for key, value in self.metadata.items():
                if key in ["author", "state", "action", "branch", "channel"]:
                    metadata_lines.append(f"  {key}: {value}")
            if metadata_lines:
                lines.append("METADATA:")
                lines.extend(metadata_lines)

        return "\n".join(lines)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Evidence(source_type={self.source_type!r}, "
            f"source_name={self.source_name!r}, "
            f"priority={self.priority})"
        )


@dataclass
class EvidenceCollection:
    """
    Collection of evidence from multiple sources.

    Provides utilities for grouping, sorting, and analyzing
    evidence across different sources.

    Attributes:
        evidence_list: List of Evidence objects
        query: Original query that generated this evidence
    """

    evidence_list: list[Evidence] = field(default_factory=list)
    query: Optional[str] = None

    def add(self, evidence: Evidence) -> None:
        """Add evidence to collection."""
        self.evidence_list.append(evidence)

    def by_source_type(self, source_type: str) -> list[Evidence]:
        """
        Get all evidence from a specific source type.

        Args:
            source_type: Source type to filter by

        Returns:
            List of matching evidence
        """
        return [e for e in self.evidence_list if e.source_type == source_type]

    def sorted_by_priority(self) -> list[Evidence]:
        """
        Get evidence sorted by priority (highest trust first).

        Returns:
            Evidence sorted by priority
        """
        return sorted(self.evidence_list, key=lambda e: e.priority)

    def sorted_by_timestamp(self, reverse: bool = True) -> list[Evidence]:
        """
        Get evidence sorted by timestamp.

        Args:
            reverse: If True, most recent first

        Returns:
            Evidence sorted by timestamp
        """
        # Filter out evidence without timestamps
        with_timestamps = [e for e in self.evidence_list if e.timestamp]
        return sorted(with_timestamps, key=lambda e: e.timestamp, reverse=reverse)

    def get_sources_used(self) -> set[str]:
        """
        Get set of source types present in this collection.

        Returns:
            Set of source type strings
        """
        return {e.source_type for e in self.evidence_list}

    def format_for_llm(self) -> str:
        """
        Format entire collection for LLM consumption.

        Returns:
            Formatted string with all evidence
        """
        if not self.evidence_list:
            return "No evidence found."

        lines = []
        if self.query:
            lines.append(f"QUERY: {self.query}")
            lines.append("")

        lines.append(f"EVIDENCE COUNT: {len(self.evidence_list)}")
        lines.append(f"SOURCES USED: {', '.join(sorted(self.get_sources_used()))}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")

        # Sort by priority for presentation
        sorted_evidence = self.sorted_by_priority()

        for i, evidence in enumerate(sorted_evidence, 1):
            lines.append(f"[EVIDENCE {i}]")
            lines.append(evidence.format_for_llm())
            lines.append("")
            lines.append("-" * 80)
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert collection to dictionary format.

        Returns:
            Dictionary representation
        """
        stats_by_source = self.stats_by_source()
        return {
            "query": self.query,
            "count": len(self.evidence_list),
            "sources_used": list(self.get_sources_used()),
            "stats_by_source": stats_by_source,
            "evidence": [e.to_dict() for e in self.evidence_list],
        }

    def stats_by_source(self) -> Dict[str, Dict[str, Any]]:
        """
        Build per-source statistics (count + latest timestamp).

        Returns:
            Dict keyed by source_type with count and latest_timestamp.
        """
        stats: Dict[str, Dict[str, Any]] = {}
        for item in self.evidence_list:
            source = str(item.source_type or "unknown")
            entry = stats.setdefault(source, {"count": 0})
            entry["count"] += 1
            if item.timestamp:
                latest_dt = entry.get("_latest_dt")
                if latest_dt is None or item.timestamp > latest_dt:
                    entry["_latest_dt"] = item.timestamp
                    entry["latest_timestamp"] = item.timestamp.isoformat()
        for entry in stats.values():
            entry.pop("_latest_dt", None)
        return stats

    def __len__(self) -> int:
        """Return number of evidence items."""
        return len(self.evidence_list)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"EvidenceCollection(count={len(self.evidence_list)}, "
            f"sources={self.get_sources_used()})"
        )
