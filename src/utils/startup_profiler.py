"""
Lightweight startup profiler shared by the backend + diagnostics tooling.

Each mark records the elapsed milliseconds since the profiler was first
created. The resulting timeline is serialized into logs/telemetry so new
engineers (or remote coding LLMs) can understand where boot time is spent.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StartupProfiler:
    """Collect ordered timestamps for startup phases."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._events: List[Dict[str, Any]] = []
        self._lock = Lock()

    def mark(self, label: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a label + elapsed milliseconds (thread-safe)."""
        with self._lock:
            elapsed_ms = round((time.perf_counter() - self._t0) * 1000, 2)
            entry = {
                "label": label,
                "elapsedMs": elapsed_ms,
            }
            if metadata:
                entry["context"] = metadata
            self._events.append(entry)
            logger.debug("[STARTUP] %s @ %.2fms", label, elapsed_ms)

    def summary(self) -> List[Dict[str, Any]]:
        """Return a copy of recorded events for logging or APIs."""
        with self._lock:
            return list(self._events)

    def reset(self) -> None:
        with self._lock:
            self._t0 = time.perf_counter()
            self._events.clear()


_PROFILER: Optional[StartupProfiler] = None


def get_startup_profiler() -> StartupProfiler:
    """Return the global profiler instance."""
    global _PROFILER
    if _PROFILER is None:
        _PROFILER = StartupProfiler()
    return _PROFILER


def reset_startup_profiler() -> None:
    """Testing helper to reset global profiler state."""
    global _PROFILER
    _PROFILER = StartupProfiler()


