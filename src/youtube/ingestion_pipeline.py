from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..graph.universal_nodes import UniversalNodeWriter
from .chunking import chunk_transcript_segments
from .graph_writer import YouTubeGraphWriter
from .metadata_client import YouTubeMetadataClient
from .models import TranscriptChunk, VideoContext
from .transcript_cache import YouTubeTranscriptCache
from .transcript_service import TranscriptProviderError, YouTubeTranscriptService
from .vector_indexer import YouTubeVectorIndexer
from .utils import build_video_alias

logger = logging.getLogger(__name__)


@dataclass
class YouTubeIngestionResult:
    video: VideoContext
    chunks: List[TranscriptChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # type: ignore[name-defined]
    reused: bool = False
    from_cache: bool = False
    vector_indexed: bool = False
    graph_ingested: bool = False
    universal_ingested: bool = False
    cache_metadata: Dict[str, Any] = field(default_factory=dict)  # type: ignore[name-defined]
    error: Optional[str] = None
    error_code: Optional[str] = None


class YouTubeIngestionPipeline:
    """Shared ingestion orchestrator for /youtube and search modalities."""

    def __init__(
        self,
        *,
        metadata_client: YouTubeMetadataClient,
        transcript_service: YouTubeTranscriptService,
        vector_indexer: YouTubeVectorIndexer,
        transcript_cache: Optional[YouTubeTranscriptCache] = None,
        graph_writer: Optional[YouTubeGraphWriter] = None,
        universal_writer: Optional[UniversalNodeWriter] = None,
        chunk_char_limit: int = 1200,
        chunk_overlap_seconds: float = 2.0,
    ):
        self.metadata_client = metadata_client
        self.transcript_service = transcript_service
        self.vector_indexer = vector_indexer
        self.transcript_cache = transcript_cache
        self.graph_writer = graph_writer
        self.universal_writer = universal_writer
        self.chunk_char_limit = chunk_char_limit
        self.chunk_overlap_seconds = chunk_overlap_seconds

    def ingest(
        self,
        context: VideoContext,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        workspace_id: str = "default_workspace",
    ) -> YouTubeIngestionResult:
        metadata = metadata or self.metadata_client.fetch_metadata(context.video_id, context.url)
        context.alias = context.alias or build_video_alias(metadata.get("title"), context.video_id, metadata.get("channel_title"))
        self._apply_metadata(context, metadata)

        result = YouTubeIngestionResult(video=context, metadata=metadata)

        if context.transcript_ready and context.chunks:
            result.chunks = context.chunks
            result.reused = True
            result.vector_indexed = True
            result.graph_ingested = True
            result.universal_ingested = True
            return result

        cached_blob = self.transcript_cache.load(context.video_id) if self.transcript_cache else None
        cache_meta = (cached_blob or {}).get("metadata") or {}
        transcript_payload: Optional[Dict[str, Any]] = None
        if cached_blob:
            chunks = self.transcript_cache.hydrate_chunks(cached_blob)
            result.chunks = chunks
            result.reused = True
            result.from_cache = True
            result.cache_metadata = cache_meta
            language = (cached_blob.get("transcript") or {}).get("language")
            transcript_payload = cached_blob.get("transcript")
            context.with_chunks(chunks)
            context.transcript_status.mark_ready(language=language)
        else:
            try:
                transcript = self.transcript_service.fetch_transcript(context.video_id)
            except TranscriptProviderError as exc:
                context.transcript_status.mark_failed(exc.code, exc.message)
                result.error = exc.message
                result.error_code = exc.code
                return result

            chunks = chunk_transcript_segments(
                context.video_id,
                transcript.get("segments") or [],
                max_chars=self.chunk_char_limit,
                overlap_seconds=self.chunk_overlap_seconds,
            )
            transcript_payload = transcript
            result.chunks = chunks
            context.with_chunks(chunks)
            context.transcript_status.mark_ready(language=transcript.get("language"))

        self._maybe_index_and_mirror(
            result,
            session_id=session_id,
            workspace_id=workspace_id,
            cache_meta=cache_meta,
        )

        self._maybe_ingest_graph(result, workspace_id=workspace_id, cache_meta=cache_meta)

        if self.transcript_cache and not result.error and transcript_payload is not None:
            cache_payload = dict(cache_meta)
            cache_payload["vector_indexed"] = result.vector_indexed
            cache_payload["graph_ingested"] = result.graph_ingested
            cache_payload["universal_ingested"] = result.universal_ingested
            cache_payload["workspace_id"] = workspace_id
            self.transcript_cache.save(
                context,
                transcript=transcript_payload,
                chunks=result.chunks,
                metadata=cache_payload,
            )

        return result

    def _maybe_index_and_mirror(
        self,
        result: YouTubeIngestionResult,
        *,
        session_id: Optional[str],
        workspace_id: str,
        cache_meta: Dict[str, Any],
    ) -> None:
        context = result.video
        needs_index = not cache_meta.get("vector_indexed")
        needs_universal = not cache_meta.get("universal_ingested")

        if not (needs_index or needs_universal):
            result.vector_indexed = bool(cache_meta.get("vector_indexed"))
            result.universal_ingested = bool(cache_meta.get("universal_ingested"))
            return

        context_chunks = None
        if (needs_index or needs_universal) and self.vector_indexer:
            context_chunks = self.vector_indexer.build_context_chunks(
                context,
                result.chunks,
                session_id=session_id,
                workspace_id=workspace_id,
            )

        if needs_index and self.vector_indexer and context_chunks is not None:
            indexed = self.vector_indexer.index_transcript(
                context,
                result.chunks,
                session_id=session_id,
                workspace_id=workspace_id,
                prebuilt_chunks=context_chunks,
            )
            result.vector_indexed = indexed
        else:
            result.vector_indexed = bool(cache_meta.get("vector_indexed"))

        if needs_universal and self.universal_writer and context_chunks:
            self.universal_writer.ingest_chunks(context_chunks)
            result.universal_ingested = True
        else:
            result.universal_ingested = bool(cache_meta.get("universal_ingested"))

    def _maybe_ingest_graph(
        self,
        result: YouTubeIngestionResult,
        *,
        workspace_id: str,
        cache_meta: Dict[str, Any],
    ) -> None:
        if cache_meta.get("graph_ingested"):
            result.graph_ingested = True
            return
        if not self.graph_writer:
            result.graph_ingested = False
            return
        ingested = self.graph_writer.ingest_video(
            result.video,
            metadata=result.metadata,
            chunks=result.chunks,
            workspace_id=workspace_id,
        )
        result.graph_ingested = ingested

    @staticmethod
    def _apply_metadata(context: VideoContext, metadata: Dict[str, Any]) -> None:
        context.title = metadata.get("title") or context.title
        context.channel_title = metadata.get("channel_title") or context.channel_title
        context.channel_id = metadata.get("channel_id") or context.channel_id
        context.description = metadata.get("description") or context.description
        context.thumbnail_url = metadata.get("thumbnail_url") or context.thumbnail_url
        context.duration_seconds = metadata.get("duration_seconds") or context.duration_seconds
        context.playlist_id = metadata.get("playlist_id") or context.playlist_id
        context.playlist_url = metadata.get("playlist_url") or context.playlist_url
        context.canonical_url = metadata.get("canonical_url") or context.canonical_url or context.url
        context.timestamp_seconds = metadata.get("timestamp_seconds") or context.timestamp_seconds
        context.tags = metadata.get("tags") or context.tags
        if context.canonical_url:
            context.url = context.canonical_url

