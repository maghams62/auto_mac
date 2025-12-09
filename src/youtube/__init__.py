"""
YouTube workflow helpers for the /youtube slash command.
"""

from .models import (
    VideoContext,
    TranscriptChunk,
    TranscriptState,
    TranscriptIngestionStatus,
)
from .utils import (
    extract_video_id,
    is_youtube_url,
    build_video_alias,
    match_video_context,
    extract_playlist_id,
    extract_timestamp_seconds,
    normalize_video_url,
    canonical_channel_identifier,
    canonical_playlist_identifier,
    slugify_text,
)
from .timestamp_parser import parse_timestamp_hint
from .history_store import YouTubeHistoryStore
from .metadata_client import YouTubeMetadataClient
from .transcript_service import YouTubeTranscriptService, TranscriptProviderError
from .chunking import chunk_transcript_segments
from .transcript_cache import YouTubeTranscriptCache
from .vector_indexer import YouTubeVectorIndexer
from .retriever import YouTubeTranscriptRetriever
from .graph_writer import YouTubeGraphWriter

__all__ = [
    "VideoContext",
    "TranscriptChunk",
    "TranscriptState",
    "TranscriptIngestionStatus",
    "extract_video_id",
    "is_youtube_url",
    "build_video_alias",
    "match_video_context",
    "parse_timestamp_hint",
    "extract_playlist_id",
    "extract_timestamp_seconds",
    "normalize_video_url",
    "canonical_channel_identifier",
    "canonical_playlist_identifier",
    "slugify_text",
    "YouTubeHistoryStore",
    "YouTubeMetadataClient",
    "YouTubeTranscriptService",
    "TranscriptProviderError",
    "chunk_transcript_segments",
    "YouTubeTranscriptCache",
    "YouTubeVectorIndexer",
    "YouTubeTranscriptRetriever",
    "YouTubeGraphWriter",
]

