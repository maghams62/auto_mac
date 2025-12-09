from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ...ingestion.slack_activity_ingestor import SlackActivityIngestor
from ...vector import VectorSearchOptions, get_vector_search_service
from ...vector.context_chunk import ContextChunk
from ..config import ModalityConfig
from .base import BaseModalityHandler

logger = logging.getLogger(__name__)


class SlackModalityHandler(BaseModalityHandler):
    """
    Modality handler that reuses the Slack activity ingestor for indexing and
    Qdrant for retrieval.
    """

    def __init__(
        self,
        modality_config: ModalityConfig,
        app_config: Dict[str, Any],
        *,
        vector_service=None,
        ingestor_factory=SlackActivityIngestor,
    ):
        super().__init__(modality_config)
        self.app_config = app_config
        self.vector_service = vector_service or get_vector_search_service(app_config)
        self.ingestor_factory = ingestor_factory

    def ingest(self, *, scope_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ingestor = self.ingestor_factory(self.app_config, vector_service=self.vector_service)
        if scope_override:
            logger.info("[SEARCH][SLACK] Scope override supplied but not yet supported: %s", scope_override)
        result = ingestor.ingest()
        ingestor.close()
        return {"messages_indexed": result.get("ingested", 0)}

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        if not self.vector_service:
            logger.warning("[SEARCH][SLACK] Vector service unavailable, returning no results")
            return []
        options = VectorSearchOptions(
            top_k=limit or self.modality_config.max_results,
            source_types=["slack"],
        )
        chunks = self.vector_service.semantic_search(query_text, options)
        return [_chunk_to_result(chunk, self.modality_config) for chunk in chunks]


def _chunk_to_result(chunk: ContextChunk, config: ModalityConfig) -> Dict[str, Any]:
    metadata = chunk.metadata or {}
    score = metadata.get("_score", 0.0)
    channel = metadata.get("channel_name") or metadata.get("channel_id") or "slack"
    user = metadata.get("user") or "unknown"
    title = f"#{channel} — {user}"
    preview = chunk.text.splitlines()
    snippet = " ".join(line.strip() for line in preview[:4]).strip()
    url = metadata.get("permalink")
    return {
        "modality": config.modality_id,
        "source_type": chunk.source_type,
        "chunk_id": chunk.chunk_id,
        "entity_id": chunk.entity_id,
        "title": title,
        "text": snippet or chunk.text[:280],
        "score": float(score) * config.weight,
        "raw_score": float(score),
        "url": url,
        "metadata": metadata,
    }

