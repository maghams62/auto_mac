"""
Simple in-memory TTL cache helpers shared by metadata services.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class CacheStats:
    """Expose basic cache metrics for diagnostics."""

    label: str
    size: int
    hits: int
    misses: int
    ttl_seconds: int


class TTLCache:
    """
    Lightweight TTL cache with coarse-grained locking.

    Designed for modest payloads (metadata lists) where the serialization
    overhead of disk-backed caches would dominate.
    """

    def __init__(self, ttl_seconds: int = 300, *, label: str = "ttl_cache"):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.label = label
        self._lock = threading.Lock()
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, *, ttl_seconds: Optional[int] = None) -> None:
        ttl = max(1, int(ttl_seconds or self.ttl_seconds))
        expires_at = time.time() + ttl
        with self._lock:
            self._store[key] = (expires_at, value)

    def invalidate(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)

    def describe(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                label=self.label,
                size=len(self._store),
                hits=self._hits,
                misses=self._misses,
                ttl_seconds=self.ttl_seconds,
            )

    def __len__(self) -> int:  # pragma: no cover - trivial wrapper
        with self._lock:
            return len(self._store)


