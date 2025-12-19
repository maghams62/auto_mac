from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..utils.component_ids import normalize_component_ids


class SignalLogWriter:
    """
    Minimal JSONL writer used to mirror live ingestion signals into
    ActivityGraph-friendly log files.
    """

    def __init__(self, path: Optional[str | Path]):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: Dict[str, Any]) -> None:
        if not self.path:
            return
        payload = self._prepare_record(record)
        serialized = json.dumps(payload, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")

    @staticmethod
    def _prepare_record(record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        component_ids = payload.get("component_ids")
        if component_ids:
            if isinstance(component_ids, Iterable) and not isinstance(component_ids, (str, bytes)):
                payload["component_ids"] = normalize_component_ids(component_ids)
            else:
                payload["component_ids"] = normalize_component_ids([component_ids])
        return payload


__all__ = ["SignalLogWriter"]

