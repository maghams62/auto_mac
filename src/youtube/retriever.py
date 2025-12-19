from __future__ import annotations

from typing import Dict, List, Optional

from ..vector import VectorSearchOptions, get_vector_search_service
from .models import TranscriptChunk, VideoContext


class YouTubeTranscriptRetriever:
    """Provide timestamp-aware and semantic retrieval over indexed transcripts."""

    def __init__(self, config, vector_service=None):
        youtube_cfg = (config.get("youtube") or {}).get("vectordb") or {}
        collection_override = youtube_cfg.get("collection")
        self.vector_service = vector_service or get_vector_search_service(
            config,
            collection_override=collection_override,
        )

    def retrieve_by_timestamp(
        self,
        video: VideoContext,
        seconds: float,
        *,
        window: float = 25.0,
    ) -> List[TranscriptChunk]:
        if not video.chunks:
            return []

        matches: List[TranscriptChunk] = []
        for chunk in video.chunks:
            if chunk.start_seconds - 2 <= seconds <= chunk.end_seconds + 2:
                matches.append(chunk)
            elif matches and chunk.start_seconds <= seconds + window:
                matches.append(chunk)
                if len(matches) >= 2:
                    break

        if matches:
            return matches

        # fallback: pick the nearest chunk
        nearest = min(
            video.chunks,
            key=lambda chunk: abs(chunk.start_seconds - seconds),
            default=None,
        )
        return [nearest] if nearest else []

    def retrieve_semantic(
        self,
        video: VideoContext,
        question: str,
        *,
        top_k: int = 4,
    ) -> List[TranscriptChunk]:
        if not self.vector_service:
            return video.chunks[:top_k]

        options = VectorSearchOptions(
            top_k=top_k,
            source_types=["youtube"],
            metadata_filters={"source_id": video.video_id},
        )
        results = self.vector_service.semantic_search(question, options)
        if not results and video.chunks:
            return video.chunks[:top_k]
        return [
            TranscriptChunk(
                video_id=video.video_id,
                index=index,
                start_seconds=chunk.metadata.get("start_offset", 0.0),
                end_seconds=chunk.metadata.get("end_offset", 0.0),
                text=chunk.text,
                token_count=chunk.metadata.get("token_count", 0),
            )
            for index, chunk in enumerate(results)
        ]

