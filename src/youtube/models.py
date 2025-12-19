from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TranscriptState(str, Enum):
    """Lifecycle states for transcript ingestion."""

    NOT_STARTED = "not_started"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


@dataclass
class TranscriptIngestionStatus:
    """Track transcript readiness and any associated errors."""

    state: TranscriptState = TranscriptState.NOT_STARTED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    language: Optional[str] = None
    last_attempted_at: Optional[str] = None

    def mark_pending(self) -> None:
        self.state = TranscriptState.PENDING
        self.error_code = None
        self.error_message = None
        self.last_attempted_at = _now_iso()

    def mark_ready(self, language: Optional[str] = None) -> None:
        self.state = TranscriptState.READY
        self.error_code = None
        self.error_message = None
        self.language = language or self.language
        self.last_attempted_at = _now_iso()

    def mark_failed(self, code: str, message: str) -> None:
        self.state = TranscriptState.FAILED
        self.error_code = code
        self.error_message = message
        self.last_attempted_at = _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TranscriptIngestionStatus":
        if not data:
            return cls()
        state_value = data.get("state") or TranscriptState.NOT_STARTED.value
        state = TranscriptState(state_value)
        return cls(
            state=state,
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
            language=data.get("language"),
            last_attempted_at=data.get("last_attempted_at"),
        )


@dataclass
class TranscriptChunk:
    """Normalized chunk structure shared across session context + Qdrant payloads."""

    video_id: str
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    token_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "index": self.index,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptChunk":
        return cls(
            video_id=data["video_id"],
            index=int(data.get("index", 0)),
            start_seconds=float(data.get("start_seconds", 0)),
            end_seconds=float(data.get("end_seconds", data.get("start_seconds", 0))),
            text=data.get("text", ""),
            token_count=int(data.get("token_count", 0)),
        )


@dataclass
class VideoContext:
    """Session-scoped representation of a YouTube video."""

    video_id: str
    url: str
    alias: str
    title: Optional[str] = None
    channel_title: Optional[str] = None
    channel_id: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    playlist_id: Optional[str] = None
    playlist_url: Optional[str] = None
    canonical_url: Optional[str] = None
    timestamp_seconds: Optional[int] = None
    transcript_status: TranscriptIngestionStatus = field(default_factory=TranscriptIngestionStatus)
    created_at: str = field(default_factory=_now_iso)
    last_used_at: str = field(default_factory=_now_iso)
    tags: List[str] = field(default_factory=list)
    chunks: List[TranscriptChunk] = field(default_factory=list)
    last_indexed_at: Optional[str] = None

    def touch(self) -> None:
        self.last_used_at = _now_iso()

    @property
    def transcript_ready(self) -> bool:
        return self.transcript_status.state == TranscriptState.READY

    def with_chunks(self, chunks: List[TranscriptChunk]) -> None:
        self.chunks = chunks
        self.last_indexed_at = _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "url": self.url,
            "alias": self.alias,
            "title": self.title,
            "channel_title": self.channel_title,
            "channel_id": self.channel_id,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "canonical_url": self.canonical_url,
            "timestamp_seconds": self.timestamp_seconds,
            "transcript_status": self.transcript_status.to_dict(),
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "tags": list(self.tags),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "last_indexed_at": self.last_indexed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoContext":
        transcript_status = TranscriptIngestionStatus.from_dict(data.get("transcript_status"))
        chunks = [TranscriptChunk.from_dict(item) for item in data.get("chunks", [])]
        return cls(
            video_id=data["video_id"],
            url=data["url"],
            alias=data.get("alias") or data["video_id"],
            title=data.get("title"),
            channel_title=data.get("channel_title"),
            channel_id=data.get("channel_id"),
            description=data.get("description"),
            thumbnail_url=data.get("thumbnail_url"),
            duration_seconds=data.get("duration_seconds"),
            playlist_id=data.get("playlist_id"),
            playlist_url=data.get("playlist_url"),
            canonical_url=data.get("canonical_url"),
            timestamp_seconds=data.get("timestamp_seconds"),
            transcript_status=transcript_status,
            created_at=data.get("created_at", _now_iso()),
            last_used_at=data.get("last_used_at", _now_iso()),
            tags=list(data.get("tags", [])),
            chunks=chunks,
            last_indexed_at=data.get("last_indexed_at"),
        )

    @classmethod
    def from_metadata(
        cls,
        video_id: str,
        url: str,
        alias: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "VideoContext":
        metadata = metadata or {}
        return cls(
            video_id=video_id,
            url=metadata.get("canonical_url") or url,
            alias=alias,
            title=metadata.get("title"),
            channel_title=metadata.get("channel_title"),
            channel_id=metadata.get("channel_id"),
            description=metadata.get("description"),
            thumbnail_url=metadata.get("thumbnail_url"),
            duration_seconds=metadata.get("duration_seconds"),
            playlist_id=metadata.get("playlist_id"),
            playlist_url=metadata.get("playlist_url"),
            canonical_url=metadata.get("canonical_url") or url,
            timestamp_seconds=metadata.get("timestamp_seconds"),
            tags=metadata.get("tags", []),
        )

    def summary_card(self) -> Dict[str, Any]:
        """Small helper used by slash responses."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel_title": self.channel_title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "canonical_url": self.canonical_url,
            "timestamp_seconds": self.timestamp_seconds,
            "alias": self.alias,
            "transcript_state": self.transcript_status.state.value,
            "transcript_error": {
                "code": self.transcript_status.error_code,
                "message": self.transcript_status.error_message,
            }
            if self.transcript_status.error_code
            else None,
            "last_used_at": self.last_used_at,
        }


def serialize_video_contexts(contexts: List[VideoContext]) -> List[Dict[str, Any]]:
    return [ctx.to_dict() for ctx in contexts]


def deserialize_video_contexts(items: List[Dict[str, Any]]) -> List[VideoContext]:
    return [VideoContext.from_dict(item) for item in items or []]

