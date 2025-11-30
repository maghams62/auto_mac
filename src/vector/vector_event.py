from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .context_chunk import ContextChunk


@dataclass
class VectorEvent:
    """Normalized vectorizable event that can be turned into a ContextChunk."""

    event_id: str
    source_type: str
    text: str
    timestamp: datetime
    service_ids: List[str] = field(default_factory=list)
    component_ids: List[str] = field(default_factory=list)
    apis: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_context_chunk(self) -> ContextChunk:
        """Convert to ContextChunk for downstream vector services."""
        chunk = ContextChunk(
            chunk_id=self.event_id,
            entity_id=self.event_id,
            source_type=self.source_type,
            text=self.text,
            component=self.component_ids[0] if self.component_ids else None,
            service=self.service_ids[0] if self.service_ids else None,
            timestamp=self.timestamp,
            tags=self._tags(),
            metadata=self._enriched_metadata(),
        )
        return chunk

    def to_record(self) -> Dict[str, Any]:
        """Serialize to dict for LocalVectorStore."""
        return {
            "event_id": self.event_id,
            "source_type": self.source_type,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "service_ids": self.service_ids,
            "component_ids": self.component_ids,
            "apis": self.apis,
            "labels": self.labels,
            "metadata": self.metadata,
            "embedding": self.embedding,
        }

    def _tags(self) -> List[str]:
        tags = set(self.labels or [])
        tags.update(self.apis or [])
        tags.update(self.service_ids or [])
        tags.update(self.component_ids or [])
        return sorted(tags)

    def _enriched_metadata(self) -> Dict[str, Any]:
        metadata = dict(self.metadata or {})
        metadata.setdefault("service_ids", self.service_ids)
        metadata.setdefault("component_ids", self.component_ids)
        metadata.setdefault("apis", self.apis)
        metadata.setdefault("labels", self.labels)
        return metadata

