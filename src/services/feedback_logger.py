"""Utility for recording user feedback (thumbs up/down) to JSONL logs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict


class FeedbackLogger:
    """Persists structured feedback entries to separate JSONL files."""

    def __init__(self, base_dir: Path | str = "data/logs") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._positive_path = self.base_dir / "feedback_positive.jsonl"
        self._negative_path = self.base_dir / "feedback_negative.jsonl"

        # Ensure files exist so downstream tooling can rely on them
        for path in (self._positive_path, self._negative_path):
            if not path.exists():
                path.touch()

        self._lock = Lock()

    def _resolve_path(self, feedback_type: str) -> Path:
        if feedback_type == "positive":
            return self._positive_path
        if feedback_type == "negative":
            return self._negative_path
        raise ValueError(f"Unsupported feedback type: {feedback_type}")

    def log(self, feedback_type: str, payload: Dict[str, Any]) -> None:
        """Write a feedback payload to the appropriate JSONL file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback_type": feedback_type,
            **payload,
        }

        target_path = self._resolve_path(feedback_type)

        with self._lock:
            with target_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True) + os.linesep)

    async def log_async(self, feedback_type: str, payload: Dict[str, Any]) -> None:
        """Async wrapper around :meth:`log` for FastAPI handlers."""
        # Local import to avoid asyncio dependency during synchronous usage
        import asyncio

        await asyncio.to_thread(self.log, feedback_type, payload)


# Singleton-style accessor --------------------------------------------------

_GLOBAL_LOGGER: FeedbackLogger | None = None


def get_feedback_logger() -> FeedbackLogger:
    global _GLOBAL_LOGGER
    if _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = FeedbackLogger()
    return _GLOBAL_LOGGER
