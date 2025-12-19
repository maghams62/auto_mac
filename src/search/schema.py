"""
search.schema
==============

Defines the universal embedding payload shared across all modalities.
Every modality should emit this schema so we can index data into Qdrant
and project nodes/edges into Neo4j consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from ..vector.context_chunk import ContextChunk


@dataclass
class UniversalEmbeddingPayload:
    """
    Canonical payload for semantic chunks regardless of modality.

    Attributes:
        workspace_id: Workspace/workstream identifier (used for tenancy).
        source_type: Modality identifier (slack/git/file/folder/youtube/web/etc).
        source_id: Stable ID for the concrete item (channel+ts, repo+path, video id).
        parent_id: Optional container identifier (workspace, repo, folder, playlist).
        display_name: Friendly title shown to humans in slash answers.
        path: Path-like identifier (folder path, repo/path, logical slug).
        start_offset/end_offset: Contextual offsets (seconds for video, row index for log, byte offset for docs).
        url: Canonical link so humans can open the source.
        modality_tags: Additional tags such as ["slack", "#incidents"].
        extra: Modality-specific metadata persisted alongside the vector.
        text: Content to embed (already chunked/clamped upstream).
        timestamp: Optional timestamp used for recency/graph projections.
        collection: Optional VectorDB collection override.
    """

    workspace_id: str
    source_type: str
    source_id: str
    parent_id: Optional[str]
    display_name: Optional[str]
    path: Optional[str]
    start_offset: Optional[float]
    end_offset: Optional[float]
    url: Optional[str]
    modality_tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    text: str = ""
    timestamp: Optional[datetime] = None
    collection: Optional[str] = None

    def ensure_tags(self) -> List[str]:
        tags = list(self.modality_tags)
        if self.source_type not in tags:
            tags.append(self.source_type)
        if self.workspace_id and self.workspace_id not in tags:
            tags.append(f"workspace:{self.workspace_id}")
        return tags


def build_context_chunk(payload: UniversalEmbeddingPayload) -> ContextChunk:
    """
    Convert a universal payload into the ContextChunk consumed by vector services.

    The translation enforces a consistent metadata contract so downstream
    RAG pipelines (folder/file/youtube/cerebros) can filter and display
    sources without modality-specific hacks.
    """

    metadata = {
        "workspace_id": payload.workspace_id,
        "source_id": payload.source_id,
        "parent_id": payload.parent_id,
        "display_name": payload.display_name,
        "path": payload.path,
        "start_offset": payload.start_offset,
        "end_offset": payload.end_offset,
        "url": payload.url,
        "extra": payload.extra,
    }

    return ContextChunk(
        chunk_id=ContextChunk.generate_chunk_id(),
        entity_id=ContextChunk.generate_entity_id(payload.source_type, payload.source_id),
        source_type=payload.source_type,
        text=ContextChunk.clamp_text(payload.text),
        timestamp=payload.timestamp,
        tags=_normalize_tags(payload.ensure_tags()),
        metadata=metadata,
        collection=payload.collection,
    )


def _normalize_tags(tags: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    for tag in tags:
        if not tag:
            continue
        normalized = tag.strip()
        if not normalized:
            continue
        cleaned.append(normalized)
    return cleaned

