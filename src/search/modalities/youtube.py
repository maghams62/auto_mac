from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from ...vector import VectorSearchOptions, get_vector_search_service
from ...vector.context_chunk import ContextChunk
from ..config import ModalityConfig
from .base import BaseModalityHandler
from ...youtube import (
    VideoContext,
    YouTubeMetadataClient,
    YouTubeTranscriptService,
    YouTubeVectorIndexer,
    extract_video_id,
    build_video_alias,
    YouTubeTranscriptCache,
    YouTubeGraphWriter,
)
from ...graph.service import GraphService
from ...graph.universal_nodes import UniversalNodeWriter
from ...youtube.ingestion_pipeline import YouTubeIngestionPipeline

logger = logging.getLogger(__name__)


class YouTubeModalityHandler(BaseModalityHandler):
    """
    Query-only handler that surfaces YouTube transcript chunks previously indexed
    via the /youtube workflow.
    """

    def __init__(
        self,
        modality_config: ModalityConfig,
        app_config: Dict[str, Any],
        *,
        vector_service=None,
        metadata_client: Optional[YouTubeMetadataClient] = None,
        transcript_service: Optional[YouTubeTranscriptService] = None,
        vector_indexer: Optional[YouTubeVectorIndexer] = None,
    ):
        super().__init__(modality_config)
        self.vector_service = vector_service or get_vector_search_service(app_config)
        self.metadata_client = metadata_client or YouTubeMetadataClient(app_config)
        self.transcript_service = transcript_service or YouTubeTranscriptService(app_config)
        self.vector_indexer = vector_indexer or YouTubeVectorIndexer(app_config, vector_service=self.vector_service)
        self.workspace_id = (app_config.get("search") or {}).get("workspace_id", "default_workspace")
        youtube_cfg = (app_config.get("youtube") or {})
        cache_cfg = (youtube_cfg.get("transcript_cache") or {})
        cache_path = Path(cache_cfg.get("path", "data/state/youtube_videos"))
        self.transcript_cache = YouTubeTranscriptCache(cache_path)
        vectordb_cfg = (youtube_cfg.get("vectordb") or {})
        self.chunk_char_limit = int(vectordb_cfg.get("max_chunk_chars", 1200))
        self.chunk_overlap_seconds = float(vectordb_cfg.get("chunk_overlap_seconds", 2.0))
        self.graph_service = GraphService(app_config)
        self.universal_writer = UniversalNodeWriter(self.graph_service)
        self.graph_writer = YouTubeGraphWriter(self.graph_service)
        self.ingestion_pipeline = YouTubeIngestionPipeline(
            metadata_client=self.metadata_client,
            transcript_service=self.transcript_service,
            vector_indexer=self.vector_indexer,
            transcript_cache=self.transcript_cache,
            graph_writer=self.graph_writer,
            universal_writer=self.universal_writer,
            chunk_char_limit=self.chunk_char_limit,
            chunk_overlap_seconds=self.chunk_overlap_seconds,
        )

    def ingest(self, *, scope_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        scope = dict(self.modality_config.scope)
        if scope_override:
            scope.update(scope_override)

        video_entries = scope.get("video_ids") or []
        if not video_entries:
            logger.info("[SEARCH][YOUTUBE] No video_ids configured; ingestion is manual via /youtube.")
            return {
                "indexed": 0,
                "videos": [],
                "manual_only": True,
                "message": "Configure search.modalities.youtube.video_ids or ingest manually via /youtube.",
            }

        indexed = 0
        failures: List[Tuple[str, str]] = []
        for entry in video_entries:
            raw = (entry or "").strip()
            if not raw:
                continue
            video_id = extract_video_id(raw) or raw if len(raw) == 11 else None
            if not video_id:
                logger.warning("[SEARCH][YOUTUBE] Could not extract video ID from %s", raw)
                failures.append((raw, "invalid_video_id"))
                continue
            success = self._ingest_video(video_id, raw if video_id != raw else None)
            if success:
                indexed += 1
            else:
                failures.append((video_id, "ingest_failed"))

        return {
            "indexed": indexed,
            "videos": video_entries,
            "failures": failures,
        }

    def _ingest_video(self, video_id: str, url: Optional[str]) -> bool:
        metadata = self.metadata_client.fetch_metadata(video_id, url)
        alias = build_video_alias(metadata.get("title"), video_id, metadata.get("channel_title"))
        context = VideoContext.from_metadata(video_id, url or metadata.get("canonical_url") or f"https://youtu.be/{video_id}", alias, metadata)
        context.transcript_status.mark_pending()

        result = self.ingestion_pipeline.ingest(
            context,
            metadata=metadata,
            session_id=None,
            workspace_id=self.workspace_id,
        )
        if result.error:
            logger.warning("[SEARCH][YOUTUBE] Ingestion failed for %s: %s", video_id, result.error)
            return False
        return True

    def can_ingest(self) -> bool:
        return True

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        if not self.vector_service:
            return []
        options = VectorSearchOptions(
            top_k=limit or self.modality_config.max_results,
            source_types=["youtube"],
        )
        chunks = self.vector_service.semantic_search(query_text, options)
        return [_chunk_to_result(chunk, self.modality_config) for chunk in chunks]


def _chunk_to_result(chunk: ContextChunk, config: ModalityConfig) -> Dict[str, Any]:
    metadata = chunk.metadata or {}
    score = metadata.get("_score", 0.0)
    title = metadata.get("display_name") or metadata.get("channel_title") or "YouTube segment"
    start_seconds = metadata.get("start_offset")
    timestamp_label = _format_timestamp(start_seconds) if start_seconds is not None else ""
    snippet = chunk.text.splitlines()[0:4]
    preview = " ".join(line.strip() for line in snippet).strip()
    url = metadata.get("url")
    if url and start_seconds is not None:
        url = f"{url}&t={int(start_seconds)}s"
    return {
        "modality": config.modality_id,
        "source_type": chunk.source_type,
        "chunk_id": chunk.chunk_id,
        "entity_id": chunk.entity_id,
        "title": f"{title} {timestamp_label}".strip(),
        "text": preview or chunk.text[:280],
        "score": float(score) * config.weight,
        "raw_score": float(score),
        "url": url,
        "metadata": metadata,
    }


def _format_timestamp(seconds: float | int) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"[{hours}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes}:{secs:02d}]"

