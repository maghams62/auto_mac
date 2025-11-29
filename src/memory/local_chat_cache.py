"""
In-memory chat cache with optional disk persistence and flush queue support.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from threading import RLock
from typing import Any, Deque, Dict, List

logger = logging.getLogger(__name__)


class LocalChatCache:
    """Stores recent chat messages per session and tracks pending flushes."""

    def __init__(
        self,
        max_messages_per_session: int = 75,
        disk_path: str = "data/cache/chat_sessions",
        flush_enabled: bool = True,
    ) -> None:
        self._max_messages = max(1, max_messages_per_session)
        self._disk_path = Path(disk_path)
        self._disk_path.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, Deque[Dict]] = {}
        self._pending: Deque[Dict] = deque()
        self._lock = RLock()
        self._flush_enabled = flush_enabled

    def append_message(self, message: Dict, persist_to_disk: bool = True) -> None:
        """Add message to in-memory cache and queue it for persistence."""
        session_id = message.get("session_id") or "default"
        with self._lock:
            bucket = self._sessions.setdefault(session_id, deque(maxlen=self._max_messages))
            bucket.append(message)
            if self._flush_enabled:
                self._pending.append(message)
            if persist_to_disk:
                self._append_to_disk(session_id, message)

    def list_recent(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Return cached messages for a session (most recent first)."""
        with self._lock:
            bucket = self._sessions.get(session_id)
            if not bucket:
                return []
            limit = max(1, limit)
            return list(bucket)[-limit:]

    def pop_flush_batch(self, batch_size: int = 50) -> List[Dict]:
        """Pop a batch of pending messages for persistence."""
        if not self._flush_enabled:
            return []
        with self._lock:
            batch: List[Dict] = []
            for _ in range(max(1, batch_size)):
                if not self._pending:
                    break
                batch.append(self._pending.popleft())
            return batch

    def describe(self) -> Dict[str, Any]:
        """Return cache configuration useful for health endpoints."""
        return {
            "max_messages_per_session": self._max_messages,
            "disk_path": str(self._disk_path),
            "flush_enabled": self._flush_enabled,
        }

    def _append_to_disk(self, session_id: str, message: Dict) -> None:
        """Persist message to JSONL file for offline recovery."""
        try:
            file_path = self._disk_path / f"{session_id}.jsonl"
            with file_path.open("a", encoding="utf-8") as handle:
                json.dump(message, handle)
                handle.write("\n")
        except Exception as exc:
            logger.debug("[CHAT CACHE] Failed to write disk cache: %s", exc)

