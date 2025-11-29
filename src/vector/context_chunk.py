"""
ContextChunk - Normalized data model for VectorDB storage.

This module defines the canonical format for chunks indexed in VectorDB.
Separate from Evidence (which is for runtime multi-source reasoning).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

MAX_VECTOR_TEXT_LENGTH = 8000


@dataclass
class ContextChunk:
    """
    Normalized context chunk for vector embedding storage.

    This is the canonical format for data indexed in VectorDB.
    Separate from Evidence (which is for runtime reasoning).

    Attributes:
        chunk_id: Unique ID for this chunk (uuid)
        entity_id: Stable entity ID (e.g., "doc:payments-guide", "pr:123")
        source_type: Type of source ("doc", "issue", "slack", "pr", "commit")
        text: Actual content to embed (will be clamped via clamp_text)
        component: Optional component name (e.g., "payments")
        service: Optional service name (e.g., "billing-service")
        timestamp: For recency filtering
        tags: Flexible tags (e.g., ["api:payments:/charge", "error:500"])
        metadata: Additional structured data
        collection: Target vector collection name (optional override)
    """

    chunk_id: str
    entity_id: str
    source_type: str
    text: str
    component: Optional[str] = None
    service: Optional[str] = None
    timestamp: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    collection: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "chunk_id": self.chunk_id,
            "entity_id": self.entity_id,
            "source_type": self.source_type,
            "text": self.text,
            "component": self.component,
            "service": self.service,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "tags": self.tags,
            "metadata": self.metadata,
            "collection": self.collection,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContextChunk:
        """
        Create ContextChunk from dictionary.

        Args:
            data: Dictionary with chunk data

        Returns:
            ContextChunk instance
        """
        timestamp = None
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            chunk_id=data["chunk_id"],
            entity_id=data["entity_id"],
            source_type=data["source_type"],
            text=data["text"],
            component=data.get("component"),
            service=data.get("service"),
            timestamp=timestamp,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            collection=data.get("collection"),
        )

    @staticmethod
    def clamp_text(text: str, max_chars: int = MAX_VECTOR_TEXT_LENGTH) -> str:
        """
        Clamp chunk text to a safe payload length.

        Args:
            text: Raw chunk text.
            max_chars: Maximum length before truncation.

        Returns:
            Clamped text with ellipsis when truncation occurs.
        """
        text = text or ""
        if len(text) <= max_chars:
            return text
        suffix = "..."
        return f"{text[: max_chars - len(suffix)]}{suffix}"

    def to_evidence(self) -> "Evidence":
        """
        Convert ContextChunk to Evidence for runtime reasoning.

        Returns:
            Evidence object
        """
        from ..agent.evidence import Evidence

        # Determine confidence based on source type
        confidence_map = {
            "git": 0.95,
            "doc": 0.85,
            "issue": 0.80,
            "slack": 0.75,
        }
        confidence = confidence_map.get(self.source_type, 0.70)

        # Format source name
        source_name_map = {
            "git": f"PR/Commit: {self.entity_id}",
            "doc": f"Doc: {self.entity_id}",
            "issue": f"Issue: {self.entity_id}",
            "slack": f"Slack: {self.entity_id}",
        }
        source_name = source_name_map.get(self.source_type, self.entity_id)

        # Map source_type to Evidence source_type
        # (Evidence uses "docs" while ContextChunk uses "doc")
        evidence_source_type = self.source_type
        if self.source_type == "doc":
            evidence_source_type = "docs"
        elif self.source_type == "issue":
            evidence_source_type = "issues"

        return Evidence(
            source_type=evidence_source_type,
            source_name=source_name,
            content=self.text,
            metadata=self.metadata,
            timestamp=self.timestamp,
            url=self.metadata.get("url"),
            confidence=confidence,
            entity_id=self.entity_id,
        )

    @staticmethod
    def generate_chunk_id() -> str:
        """
        Generate a unique chunk ID.

        Returns:
            UUID string
        """
        return str(uuid.uuid4())

    @staticmethod
    def generate_entity_id(source_type: str, identifier: str) -> str:
        """
        Generate a stable entity ID following the convention.

        Format: {type}:{identifier}

        Args:
            source_type: Type of entity (doc, issue, pr, slack, etc.)
            identifier: Unique identifier for the entity

        Returns:
            Entity ID string

        Examples:
            >>> generate_entity_id("doc", "payments-guide")
            "doc:payments-guide"
            >>> generate_entity_id("pr", "123")
            "pr:123"
        """
        return f"{source_type}:{identifier}"

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"ContextChunk(entity_id={self.entity_id!r}, "
            f"source_type={self.source_type!r}, "
            f"text={self.text[:50]!r}...)"
        )


# Entity ID generation utilities

def generate_doc_entity_id(doc_path: str) -> str:
    """
    Generate entity ID for a documentation page.

    Args:
        doc_path: Path or slug for the doc (e.g., "payments-guide", "api/authentication")

    Returns:
        Entity ID in format "doc:{path}"
    """
    # Normalize path: remove leading/trailing slashes, convert to lowercase
    normalized = doc_path.strip("/").lower().replace(" ", "-")
    return f"doc:{normalized}"


def generate_issue_entity_id(issue_number: int) -> str:
    """
    Generate entity ID for a GitHub issue.

    Args:
        issue_number: Issue number

    Returns:
        Entity ID in format "issue:{number}"
    """
    return f"issue:{issue_number}"


def generate_pr_entity_id(pr_number: int) -> str:
    """
    Generate entity ID for a pull request.

    Args:
        pr_number: PR number

    Returns:
        Entity ID in format "pr:{number}"
    """
    return f"pr:{pr_number}"


def generate_slack_entity_id(channel_id: str, timestamp: str) -> str:
    """
    Generate entity ID for a Slack message.

    Args:
        channel_id: Slack channel ID (e.g., "C123ABC")
        timestamp: Slack timestamp (e.g., "1701111111.0001")

    Returns:
        Entity ID in format "slack:{channel}:{timestamp}"
    """
    return f"slack:{channel_id}:{timestamp}"


def generate_commit_entity_id(commit_hash: str) -> str:
    """
    Generate entity ID for a Git commit.

    Args:
        commit_hash: Commit SHA hash

    Returns:
        Entity ID in format "commit:{hash}"
    """
    # Use first 7 chars of hash for readability
    short_hash = commit_hash[:7] if len(commit_hash) > 7 else commit_hash
    return f"commit:{short_hash}"


def parse_entity_id(entity_id: str) -> tuple[str, str]:
    """
    Parse an entity ID into type and identifier.

    Args:
        entity_id: Entity ID string (e.g., "doc:payments-guide")

    Returns:
        Tuple of (type, identifier)

    Raises:
        ValueError: If entity ID format is invalid
    """
    if ":" not in entity_id:
        raise ValueError(f"Invalid entity ID format: {entity_id}")

    parts = entity_id.split(":", 1)
    return parts[0], parts[1]
