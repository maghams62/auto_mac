"""
Evidence Model - Unified representation for multi-source data.

This module provides a normalized Evidence format that abstracts over
different data sources (Git PRs, Slack messages, docs, issues, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


# Source priority hierarchy (lower number = higher trust)
SOURCE_PRIORITY = {
    "git": 1,                # Code changes are ground truth
    "docs": 2,               # Official documentation
    "activity_graph": 2.5,   # Aggregated multi-signal insights
    "issues": 3,             # Tracked issues/bugs
    "slack": 4,              # Team discussions
    "unknown": 99,           # Fallback
}

# Human-readable source descriptions
SOURCE_DESCRIPTIONS = {
    "git": "Git commit/PR",
    "docs": "Documentation",
    "activity_graph": "Activity graph analytics",
    "issues": "Issue tracker",
    "slack": "Slack discussion",
    "unknown": "Unknown source",
}


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
        return SOURCE_PRIORITY.get(self.source_type, SOURCE_PRIORITY["unknown"])

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
        return {
            "query": self.query,
            "count": len(self.evidence_list),
            "sources_used": list(self.get_sources_used()),
            "evidence": [e.to_dict() for e in self.evidence_list],
        }

    def __len__(self) -> int:
        """Return number of evidence items."""
        return len(self.evidence_list)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"EvidenceCollection(count={len(self.evidence_list)}, "
            f"sources={self.get_sources_used()})"
        )
