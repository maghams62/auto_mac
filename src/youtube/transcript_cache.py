from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .models import TranscriptChunk, VideoContext

logger = logging.getLogger(__name__)


class YouTubeTranscriptCache:
    """Persist raw transcripts and chunked windows for reuse across sessions."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def load(self, video_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(video_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - corrupted cache entries
            logger.warning("[YOUTUBE][CACHE] Failed to load cache for %s: %s", video_id, exc)
            return None

    def save(
        self,
        video: VideoContext,
        *,
        transcript: Dict[str, Any],
        chunks: List[TranscriptChunk],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        path = self._path_for(video.video_id)
        meta_payload = {
            "cached_at": video.last_indexed_at,
        }
        if metadata:
            meta_payload.update(metadata)
        payload = {
            "video": video.summary_card(),
            "transcript": {
                "language": transcript.get("language"),
                "segments": transcript.get("segments") or [],
            },
            "chunks": [chunk.to_dict() for chunk in chunks],
            "metadata": meta_payload,
        }
        try:
            with self._lock:
                path.write_text(json.dumps(payload, indent=2))
        except Exception as exc:  # pragma: no cover - IO errors surfaced via logs
            logger.warning("[YOUTUBE][CACHE] Failed to persist cache for %s: %s", video.video_id, exc)

    def hydrate_chunks(self, cached: Dict[str, Any]) -> List[TranscriptChunk]:
        items = cached.get("chunks") or []
        return [TranscriptChunk.from_dict(item) for item in items]

    def _path_for(self, video_id: str) -> Path:
        sanitized = "".join(char if char.isalnum() else "_" for char in video_id)
        return self.root / f"{sanitized}.json"


