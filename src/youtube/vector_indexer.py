from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..vector import ContextChunk, get_vector_search_service
from .models import TranscriptChunk, VideoContext

logger = logging.getLogger(__name__)


class YouTubeVectorIndexer:
    """Indexes transcript chunks into the dedicated YouTube Qdrant collection."""

    def __init__(self, config: Dict[str, any], vector_service=None):
        youtube_cfg = (config.get("youtube") or {}).get("vectordb") or {}
        collection_override = youtube_cfg.get("collection")
        self.config = config
        self.vector_service = vector_service or get_vector_search_service(
            config,
            collection_override=collection_override,
        )
        self.collection = collection_override or (getattr(self.vector_service, "collection", None) if self.vector_service else None)

    def index_transcript(
        self,
        video: VideoContext,
        chunks: List[TranscriptChunk],
        *,
        session_id: Optional[str],
        workspace_id: str = "default_workspace",
        prebuilt_chunks: Optional[List[ContextChunk]] = None,
    ) -> bool:
        if not chunks:
            logger.info("[YOUTUBE] No transcript chunks to index for %s", video.video_id)
            return False
        if not self.vector_service:
            logger.info("[YOUTUBE] Vector service unavailable; skipping indexing for %s", video.video_id)
            return False

        context_chunks = prebuilt_chunks or self.build_context_chunks(
            video,
            chunks,
            session_id=session_id,
            workspace_id=workspace_id,
        )
        success = self.vector_service.index_chunks(context_chunks)
        if success:
            logger.info("[YOUTUBE] Indexed %s transcript chunks for %s", len(context_chunks), video.video_id)
        return success

    def build_context_chunks(
        self,
        video: VideoContext,
        chunks: List[TranscriptChunk],
        *,
        session_id: Optional[str],
        workspace_id: str,
    ) -> List[ContextChunk]:
        return [
            self._to_context_chunk(video, chunk, session_id, workspace_id)
            for chunk in chunks
        ]

    def _to_context_chunk(
        self,
        video: VideoContext,
        chunk: TranscriptChunk,
        session_id: Optional[str],
        workspace_id: str,
    ) -> ContextChunk:
        timestamp_card = _format_timestamp(chunk.start_seconds)
        header = f"{video.title or video.video_id} ({timestamp_card})"
        text = f"{header}\nChannel: {video.channel_title or 'Unknown'}\n\n{chunk.text}"

        metadata = {
            "source_id": video.video_id,
            "video_id": video.video_id,
            "display_name": video.title or video.video_id,
            "start_offset": chunk.start_seconds,
            "end_offset": chunk.end_seconds,
            "workspace_id": workspace_id,
            "session_id": session_id,
            "url": video.url,
            "canonical_url": video.canonical_url,
            "channel_title": video.channel_title,
            "channel_id": video.channel_id,
            "playlist_id": video.playlist_id,
            "playlist_url": video.playlist_url,
            "alias": video.alias,
            "token_count": chunk.token_count,
            "source_type": "youtube",
        }

        tags = ["youtube", f"video:{video.video_id}"]
        if video.channel_title:
            tags.append(video.channel_title.lower().replace(" ", "-"))
        if video.channel_id:
            tags.append(f"channel:{video.channel_id}")
        if video.playlist_id:
            tags.append(f"playlist:{video.playlist_id}")
        tags.extend(video.tags or [])

        return ContextChunk(
            chunk_id=ContextChunk.generate_chunk_id(),
            entity_id=f"youtube:{video.video_id}:{int(chunk.start_seconds)}",
            source_type="youtube",
            text=text,
            component=None,
            service=None,
            tags=tags,
            metadata=metadata,
            collection=self.collection,
        )


def _format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"

