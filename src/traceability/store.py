"""
Simple JSON-backed store for investigation records.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceabilityStore:
    """
    Persistence helper for investigations + evidence metadata.

    Stores a capped list of records in JSON (not JSONL) to keep things easy to inspect.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: Path,
        *,
        max_entries: int = 500,
        retention_days: int = 30,
        max_bytes: int = 5 * 1024 * 1024,
    ):
        self.path = path
        self.max_entries = max(1, max_entries)
        self.retention_days = max(0, retention_days)
        self.max_bytes = max(64 * 1024, max_bytes)  # Minimum 64KB to avoid thrashing
        self._lock = Lock()
        self.enabled = bool(self.path)
        self._last_error: Optional[Dict[str, Any]] = None
        self._last_write_at: Optional[str] = None
        self._last_count: int = 0

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a record to the store (trimmed to `max_entries`).
        """
        if not self.enabled:
            return record

        record = self._apply_defaults(record)
        record.setdefault("schema_version", self.SCHEMA_VERSION)
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())

        with self._lock:
            try:
                records = self._load()
                records.append(record)
                records = self._apply_retention(records)
                self._write(records)
                self._last_error = None
                self._last_write_at = datetime.now(timezone.utc).isoformat()
                self._last_count = len(records)
            except Exception as exc:
                self._last_error = {
                    "message": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                logger.warning("[TRACEABILITY] Failed to append investigation: %s", exc)
                raise
        return record

    def list(self, *, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Return the most recent investigations (newest first).
        """
        if not self.enabled:
            return []
        limit = max(1, min(limit, self.max_entries))
        records = self._load()
        subset = records[-limit:]
        return list(reversed(subset))

    def get(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        """
        Return a single investigation by id (latest wins).
        """
        if not self.enabled:
            return None
        if not investigation_id:
            return None
        for record in reversed(self._load()):
            if record.get("id") == investigation_id:
                return record
        return None

    def describe(self) -> Dict[str, Any]:
        """
        Lightweight health summary for /health endpoints.
        """
        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "max_entries": self.max_entries,
            "retention_days": self.retention_days,
             "max_file_bytes": self.max_bytes,
            "schema_version": self.SCHEMA_VERSION,
            "last_write_at": self._last_write_at,
            "last_error": self._last_error,
            "records_cached": self._last_count,
        }

    # ------------------------------------------------------------------
    # Internal helpers

    def _load(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8")) or []
            normalized: List[Dict[str, Any]] = []
            for entry in payload:
                normalized_entry = self._apply_defaults(entry)
                if normalized_entry:
                    normalized.append(normalized_entry)
            return normalized
        except json.JSONDecodeError as exc:
            logger.warning("[TRACEABILITY] Corrupted investigations file %s: %s", self.path, exc)
            return []

    def _write(self, records: List[Dict[str, Any]]) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure max_entries guard even after retention
        if len(records) > self.max_entries:
            records = records[-self.max_entries :]
        self.path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
        self._enforce_file_size(records)

    def _apply_retention(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.retention_days <= 0:
            return records
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        pruned: List[Dict[str, Any]] = []
        for record in records:
            created_at = record.get("created_at")
            keep = True
            if isinstance(created_at, str):
                try:
                    keep = datetime.fromisoformat(created_at.replace("Z", "+00:00")) >= cutoff
                except ValueError:
                    keep = True
            if keep:
                pruned.append(record)
        return pruned

    def _enforce_file_size(self, records: List[Dict[str, Any]]) -> None:
        if self.max_bytes <= 0 or not self.path.exists():
            return
        size = self.path.stat().st_size
        if size <= self.max_bytes:
            return
        trimmed = records
        while trimmed and size > self.max_bytes:
            trimmed = trimmed[1:]
            self.path.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False))
            size = self.path.stat().st_size
        self._last_count = len(trimmed)

    def _apply_defaults(self, record: Any) -> Dict[str, Any]:
        if not isinstance(record, dict):
            return {}

        normalized = dict(record)
        record_type = str(normalized.get("type") or "investigation").lower()
        normalized["type"] = record_type if record_type in {"investigation", "incident"} else "investigation"

        summary = normalized.get("summary")
        if not summary:
            summary_source = normalized.get("question") or normalized.get("goal") or normalized.get("answer")
            if summary_source:
                normalized["summary"] = str(summary_source)[:240]

        if "severity" not in normalized:
            normalized["severity"] = None
        if "blast_radius_score" not in normalized:
            normalized["blast_radius_score"] = None
        if "source_command" not in normalized:
            normalized["source_command"] = None
        if "raw_trace_id" not in normalized:
            normalized["raw_trace_id"] = None
        if "status" not in normalized and normalized["type"] == "incident":
            normalized["status"] = "open"

        return normalized

