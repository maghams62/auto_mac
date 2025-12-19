from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, Optional, Sequence

from ..graph.ingestor import GraphIngestor
from ..graph.service import GraphService
from .models import TranscriptChunk, VideoContext
from .utils import (
    canonical_channel_identifier,
    canonical_playlist_identifier,
)

logger = logging.getLogger(__name__)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class YouTubeGraphWriter:
    """
    Persist YouTube videos, channels, playlists, and transcript chunks into Neo4j.

    This writer mirrors the ingestion style used by Slack/Git so /youtube becomes
    a first-class source inside the activity graph.
    """

    def __init__(self, graph_service: Optional[GraphService]):
        self.graph_service = graph_service
        self.ingestor = GraphIngestor(graph_service) if graph_service else None

    def available(self) -> bool:
        return bool(self.ingestor and self.graph_service and self.graph_service.is_available())

    def ingest_video(
        self,
        video: VideoContext,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        chunks: Optional[Iterable[TranscriptChunk]] = None,
        workspace_id: Optional[str] = None,
        concept_annotations: Optional[Dict[str, Sequence[str]]] = None,
    ) -> bool:
        """
        Upsert the video graph and (optionally) transcript chunk nodes.

        Args:
            video: Session video context.
            metadata: Enriched metadata from YouTubeMetadataClient.
            chunks: Transcript chunks ready for graph linking.
            workspace_id: Workspace identifier for multi-tenant graphs.
            concept_annotations: Optional map of chunk_id -> [concept labels].
        """
        if not self.available():
            return False

        metadata = metadata or {}
        try:
            video_props = self._build_video_properties(video, metadata, workspace_id)
            self.ingestor.upsert_video(video.video_id, video_props)

            channel_id = canonical_channel_identifier(
                metadata.get("channel_id"),
                metadata.get("channel_title") or video.channel_title,
            )
            if channel_id:
                channel_props = {
                    "title": metadata.get("channel_title") or video.channel_title,
                    "url": metadata.get("channel_url"),
                }
                self.ingestor.upsert_channel(channel_id, channel_props)
                self.ingestor.link_video_channel(video.video_id, channel_id)

            playlist_id = canonical_playlist_identifier(
                metadata.get("playlist_id"),
                metadata.get("channel_title") or video.channel_title,
            )
            if playlist_id:
                playlist_props = {
                    "title": metadata.get("playlist_title"),
                    "url": metadata.get("playlist_url"),
                }
                self.ingestor.upsert_playlist(playlist_id, playlist_props)
                self.ingestor.link_video_playlist(video.video_id, playlist_id)

            if chunks:
                self._ingest_chunks(
                    video_id=video.video_id,
                    chunks=chunks,
                    workspace_id=workspace_id,
                    concept_annotations=concept_annotations,
                )

            return True
        except Exception as exc:  # pragma: no cover - defensive log
            logger.warning("[YOUTUBE][GRAPH] Failed to ingest %s: %s", video.video_id, exc)
            return False

    def _ingest_chunks(
        self,
        *,
        video_id: str,
        chunks: Iterable[TranscriptChunk],
        workspace_id: Optional[str],
        concept_annotations: Optional[Dict[str, Sequence[str]]] = None,
    ) -> None:
        concept_annotations = concept_annotations or {}
        for chunk in chunks:
            chunk_node_id = self._chunk_node_id(video_id, chunk.index)
            props = {
                "video_id": video_id,
                "start_seconds": chunk.start_seconds,
                "end_seconds": chunk.end_seconds,
                "text_preview": (chunk.text or "")[:280],
                "token_count": chunk.token_count,
                "workspace_id": workspace_id,
            }
            self.ingestor.upsert_transcript_chunk(chunk_node_id, props)
            self.ingestor.link_video_chunk(video_id, chunk_node_id)

            concept_names = concept_annotations.get(chunk_node_id) or concept_annotations.get(str(chunk.index))
            if concept_names:
                self._link_concepts(chunk_node_id, concept_names)

    def _link_concepts(self, chunk_id: str, concept_names: Sequence[str]) -> None:
        for name in concept_names:
            concept_id = self._concept_node_id(name)
            if not concept_id:
                continue
            self.ingestor.upsert_concept(concept_id, {"name": name})
            self.ingestor.link_chunk_concept(chunk_id, concept_id)

    @staticmethod
    def _chunk_node_id(video_id: str, chunk_index: int) -> str:
        return f"{video_id}:{chunk_index}"

    @staticmethod
    def _concept_node_id(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        slug = _SLUG_PATTERN.sub("-", name.lower()).strip("-")
        if not slug:
            return None
        return f"concept:{slug}"

    @staticmethod
    def _build_video_properties(
        video: VideoContext,
        metadata: Dict[str, Any],
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        tags = metadata.get("tags") or video.tags or []
        props = {
            "title": video.title or metadata.get("title"),
            "alias": video.alias,
            "url": metadata.get("canonical_url") or video.url,
            "source_url": video.url,
            "thumbnail_url": video.thumbnail_url or metadata.get("thumbnail_url"),
            "description": video.description or metadata.get("description"),
            "duration_seconds": video.duration_seconds or metadata.get("duration_seconds"),
            "channel_title": video.channel_title or metadata.get("channel_title"),
            "workspace_id": workspace_id,
            "tags": tags,
            "published_at": metadata.get("published_at"),
            "playlist_id": metadata.get("playlist_id"),
            "timestamp_seconds": metadata.get("timestamp_seconds"),
        }
        # Remove None values to avoid overwriting existing graph nodes with nulls
        return {key: value for key, value in props.items() if value is not None}

