"""
Startup cache helpers.

The Electron shell spawns the Python backend on every launch. A cold start
means we rebuild prompt bundles, agent manifests, and config snapshots before
requests can flow – even though those artifacts rarely change. The
`StartupCacheManager` below persists that expensive work to `data/cache/`
between launches so the backend can hydrate itself instantly.

Design goals:
-------------
1. **Safe invalidation** — Cache keys include the config path plus prompt
   directories; touching those files invalidates the cache automatically.
2. **Human-readable** — Cache files are JSON for easy inspection when
   debugging on a customer machine.
3. **Telemetry-friendly** — Every load/save emits structured `[STARTUP]` logs
   so we can trace cache hit-rates in production.
"""

from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)


class StartupCacheManager:
    """
    Persist warm-start payloads to disk with automatic invalidation.

    Typical usage:

    >>> cache = StartupCacheManager("data/cache/startup_bootstrap.json", [...paths])
    >>> payload = cache.load_section("automation_bootstrap")
    >>> if payload:
    ...     hydrate_agent(payload)
    >>> else:
    ...     payload = build_payload()
    ...     cache.save_section("automation_bootstrap", payload)
    """

    def __init__(
        self,
        cache_path: str,
        fingerprint_sources: Iterable[Path],
    ) -> None:
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.fingerprint_sources = tuple(Path(src) for src in fingerprint_sources)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load_section(self, section: str) -> Optional[Dict[str, Any]]:
        """Return a cached section if the fingerprint is still valid."""
        blob = self._read_cache()
        if not blob:
            return None

        payload = blob.get("payload") or {}
        section_payload = payload.get(section)
        if section_payload:
            logger.info("[STARTUP] Cache hit for section '%s'", section)
        else:
            logger.info("[STARTUP] Cache miss for section '%s' (section absent)", section)
        return section_payload

    def save_section(self, section: str, data: Dict[str, Any]) -> None:
        """
        Write/overwrite a section in the cache.

        This recomputes the fingerprint so future launches invalidate stale data
        when config or prompt files change.
        """
        blob = self._read_cache(ignore_fingerprint=True) or {
            "fingerprint": None,
            "created_at": None,
            "payload": {},
            "version": 1,
        }
        payload = blob.get("payload") or {}
        payload[section] = data
        blob["payload"] = payload
        blob["created_at"] = datetime.now(timezone.utc).isoformat()
        blob["fingerprint"] = self._compute_fingerprint()
        blob["version"] = 1
        self._write_cache(blob)
        logger.info(
            "[STARTUP] Cache section '%s' persisted (bytes=%d)",
            section,
            len(json.dumps(data)),
        )

    def describe(self) -> Dict[str, Any]:
        """Expose cache metadata for diagnostics endpoints."""
        blob = self._read_cache(ignore_fingerprint=True) or {}
        return {
            "cache_path": str(self.cache_path),
            "fingerprint_sources": [str(src) for src in self.fingerprint_sources],
            "fingerprint": blob.get("fingerprint"),
            "last_updated": blob.get("created_at"),
            "sections": list((blob.get("payload") or {}).keys()),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _compute_fingerprint(self) -> str:
        """
        Hash config + prompt trees.

        We only care about modification time + size, which keeps the hash cheap
        and still invalidates on any edit.
        """
        digest = hashlib.sha256()
        for source in sorted(self.fingerprint_sources, key=lambda p: str(p)):
            if not source.exists():
                continue
            if source.is_file():
                digest.update(self._stat_bytes(source))
            else:
                for child in sorted(source.rglob("*")):
                    if child.is_file():
                        digest.update(self._stat_bytes(child))
        return digest.hexdigest()

    def _stat_bytes(self, path: Path) -> bytes:
        stat = path.stat()
        return f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")

    def _read_cache(self, ignore_fingerprint: bool = False) -> Optional[Dict[str, Any]]:
        if not self.cache_path.exists():
            return None
        try:
            blob = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[STARTUP] Failed to read cache %s: %s", self.cache_path, exc)
            return None

        if ignore_fingerprint:
            return blob

        expected = self._compute_fingerprint()
        if blob.get("fingerprint") != expected:
            logger.info(
                "[STARTUP] Cache invalidated (fingerprint mismatch) expected=%s actual=%s",
                expected[:12],
                str(blob.get("fingerprint"))[:12],
            )
            return None

        return blob

    def _write_cache(self, blob: Dict[str, Any]) -> None:
        tmp_path = self.cache_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        tmp_path.replace(self.cache_path)


