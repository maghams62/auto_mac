"""
Simple JSON-backed state storage for activity ingestion cursors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ActivityIngestState:
    """
    Manages ingestion cursors (last timestamps, SHAs, etc.) on disk.
    """

    def __init__(self, base_dir: str = "data/state/activity_ingest"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, key: str) -> Dict[str, Any]:
        """
        Load the stored state for the given key.
        """
        path = self._path_for_key(key)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return {}

    def save(self, key: str, data: Dict[str, Any]) -> None:
        """
        Persist state for the given key (atomic write).
        """
        path = self._path_for_key(key)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        tmp_path.replace(path)

    def _path_for_key(self, key: str) -> Path:
        safe_key = key.replace("/", "_")
        return self.base_dir / f"{safe_key}.json"

