from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ...ingestion.git_activity_ingestor import GitActivityIngestor
from ...vector import VectorSearchOptions, get_vector_search_service
from ...vector.context_chunk import ContextChunk
from ..config import ModalityConfig
from .base import BaseModalityHandler

logger = logging.getLogger(__name__)


class GitModalityHandler(BaseModalityHandler):
    """
    Modality handler for Git/GitHub activity.
    """

    def __init__(
        self,
        modality_config: ModalityConfig,
        app_config: Dict[str, Any],
        *,
        vector_service=None,
        ingestor_factory=GitActivityIngestor,
    ):
        super().__init__(modality_config)
        self.app_config = app_config
        self.vector_service = vector_service or get_vector_search_service(app_config)
        self.ingestor_factory = ingestor_factory

    def ingest(self, *, scope_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ingestor = self.ingestor_factory(self.app_config, vector_service=self.vector_service)
        if scope_override:
            logger.info("[SEARCH][GIT] Scope override supplied but not yet supported: %s", scope_override)
        result = ingestor.ingest()
        ingestor.close()
        return {
            "prs": result.get("prs", 0),
            "commits": result.get("commits", 0),
            "issues": result.get("issues", 0),
        }

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        if not self.vector_service:
            logger.warning("[SEARCH][GIT] Vector service unavailable, returning no results")
            return []
        options = VectorSearchOptions(
            top_k=limit or self.modality_config.max_results,
            source_types=["git"],
        )
        chunks = self.vector_service.semantic_search(query_text, options)
        return [_chunk_to_result(chunk, self.modality_config) for chunk in chunks]


def _chunk_to_result(chunk: ContextChunk, config: ModalityConfig) -> Dict[str, Any]:
    metadata = chunk.metadata or {}
    score = metadata.get("_score", 0.0)
    entity_id = chunk.entity_id
    title = metadata.get("title") or entity_id
    url = metadata.get("url") or metadata.get("permalink")
    snippet = chunk.text.splitlines()[0:6]
    preview = " ".join(line.strip() for line in snippet).strip()
    return {
        "modality": config.modality_id,
        "source_type": chunk.source_type,
        "chunk_id": chunk.chunk_id,
        "entity_id": chunk.entity_id,
        "title": title,
        "text": preview or chunk.text[:280],
        "score": float(score) * config.weight,
        "raw_score": float(score),
        "url": url,
        "metadata": metadata,
    }

