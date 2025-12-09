from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, List, Optional

from ..automation.clipboard_tools import read_clipboard
from .utils import extract_video_id, is_youtube_url

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ClipboardReader = Callable[[], Dict[str, str]]


@dataclass
class HistoryEntry:
    url: str
    video_id: Optional[str]
    title: Optional[str]
    last_used_at: str
    channel_title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[str] = None
    source: str = "session"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "HistoryEntry":
        return cls(
            url=data.get("url", ""),
            video_id=data.get("video_id"),
            title=data.get("title"),
            last_used_at=data.get("last_used_at", ""),
            channel_title=data.get("channel_title"),
            description=data.get("description"),
            thumbnail_url=data.get("thumbnail_url"),
            created_at=data.get("created_at"),
            source=data.get("source", "session"),
        )


class YouTubeHistoryStore:
    """Persist MRU YouTube URLs per-machine, with optional clipboard awareness."""

    def __init__(
        self,
        path: Path,
        max_entries: int = 8,
        clipboard_enabled: bool = True,
        clipboard_reader: Optional[ClipboardReader] = None,
    ):
        self.path = path
        self.max_entries = max_entries
        self.clipboard_enabled = clipboard_enabled
        self.clipboard_reader = clipboard_reader or read_clipboard
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: HistoryEntry) -> None:
        entry.created_at = entry.created_at or _now_iso()
        with self._lock:
            entries = self._load_entries()
            filtered = [e for e in entries if e.url != entry.url]
            filtered.insert(0, entry)
            trimmed = filtered[: self.max_entries]
            self._save_entries(trimmed)

    def get_recent(self, limit: Optional[int] = None) -> List[HistoryEntry]:
        entries = self._load_entries()
        limit = limit or self.max_entries
        return entries[:limit]

    def search(self, query: Optional[str], limit: int) -> List[HistoryEntry]:
        entries = self._load_entries()
        if not query:
            return entries[:limit]
        normalized = query.strip().lower()
        if not normalized:
            return entries[:limit]

        matches: List[HistoryEntry] = []
        for entry in entries:
            haystacks = [
                (entry.title or "").lower(),
                (entry.channel_title or "").lower(),
            ]
            if any(normalized in hay for hay in haystacks if hay):
                matches.append(entry)
            if len(matches) >= limit:
                break
        return matches

    def get_suggestions(self, limit: int, include_clipboard: bool = True) -> Dict[str, List[Dict[str, str]]]:
        recent = [entry.to_dict() for entry in self.get_recent(limit)]
        clipboard = []
        if include_clipboard and self.clipboard_enabled:
            clipboard = self._read_clipboard_candidates(limit)
        return {"recent": recent, "clipboard": clipboard}

    def _read_clipboard_candidates(self, limit: int) -> List[Dict[str, str]]:
        try:
            result = self.clipboard_reader()
        except Exception as exc:
            logger.debug("[YOUTUBE] Clipboard read failed: %s", exc)
            return []

        content = (result or {}).get("content", "").strip()
        if not content or not is_youtube_url(content):
            return []

        video_id = extract_video_id(content)
        if not video_id:
            return []

        return [
            {
                "url": content,
                "video_id": video_id,
                "title": None,
                "source": "clipboard",
            }
        ][:limit]

    def _load_entries(self) -> List[HistoryEntry]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            return [HistoryEntry.from_dict(entry) for entry in data.get("entries", [])]
        except Exception as exc:
            logger.warning("[YOUTUBE] Failed to read history store: %s", exc)
            return []

    def _save_entries(self, entries: List[HistoryEntry]) -> None:
        payload = {"entries": [entry.to_dict() for entry in entries]}
        try:
            self.path.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            logger.warning("[YOUTUBE] Failed to persist history store: %s", exc)

