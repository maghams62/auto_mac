from __future__ import annotations

import logging
from typing import Iterable, Optional, Dict, Any

from ..vector.context_chunk import ContextChunk
from .schema import NodeLabels, RelationshipTypes
from .service import GraphService

logger = logging.getLogger(__name__)


class UniversalNodeWriter:
    """
    Small helper that mirrors universal embedding chunks into the Neo4j graph.
    """

    def __init__(self, graph_service: Optional[GraphService]):
        self.graph_service = graph_service

    def available(self) -> bool:
        return bool(self.graph_service and self.graph_service.is_available())

    def ingest_chunks(self, chunks: Iterable[ContextChunk]) -> None:
        if not self.available():
            return
        for chunk in chunks:
            try:
                self._upsert_chunk(chunk)
            except Exception as exc:  # pragma: no cover - defensive log
                logger.warning("[GRAPH][CHUNK] Failed to upsert chunk %s: %s", chunk.chunk_id, exc)

    # ------------------------------------------------------------------ #
    def _upsert_chunk(self, chunk: ContextChunk) -> None:
        metadata = chunk.metadata or {}
        source_id = metadata.get("source_id") or chunk.entity_id
        parent_id = metadata.get("parent_id")
        workspace_id = metadata.get("workspace_id")

        source_props = _clean_dict(
            {
                "source_type": metadata.get("source_type") or chunk.source_type,
                "display_name": metadata.get("display_name") or metadata.get("title"),
                "path": metadata.get("path"),
                "parent_id": parent_id,
                "workspace_id": workspace_id,
            }
        )

        chunk_props = _clean_dict(
            {
                "entity_id": chunk.entity_id,
                "source_type": chunk.source_type,
                "component": chunk.component,
                "service": chunk.service,
                "workspace_id": workspace_id,
                "start_offset": metadata.get("start_offset"),
                "end_offset": metadata.get("end_offset"),
                "url": metadata.get("url"),
                "alias": metadata.get("alias"),
                "text_preview": (chunk.text or "")[:280],
            }
        )

        params = {
            "source_id": source_id,
            "source_props": source_props,
            "chunk_id": chunk.chunk_id,
            "chunk_props": chunk_props,
        }

        query = f"""
        MERGE (source:{NodeLabels.SOURCE.value} {{id: $source_id}})
        ON CREATE SET source.created_at = timestamp()
        SET source += $source_props

        MERGE (chunk:{NodeLabels.CHUNK.value} {{id: $chunk_id}})
        ON CREATE SET chunk.created_at = timestamp()
        SET chunk += $chunk_props

        MERGE (chunk)-[:{RelationshipTypes.BELONGS_TO.value}]->(source)
        """
        self.graph_service.run_write(query, params=params)


def _clean_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}

