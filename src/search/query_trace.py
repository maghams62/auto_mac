from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TRACE_STORE_PATH = Path(os.getenv("QUERY_TRACE_PATH", "data/state/query_traces.jsonl"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(mapping or {}, default=_json_default))
    except Exception:
        return {}


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _json_clone(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(payload, default=_json_default))
    except Exception:
        return payload


@dataclass
class ChunkRef:
    chunk_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    modality: Optional[str] = None
    title: Optional[str] = None
    score: Optional[float] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = _sanitize_mapping(self.metadata)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ChunkRef":
        return cls(
            chunk_id=payload.get("chunk_id"),
            source_type=payload.get("source_type"),
            source_id=payload.get("source_id"),
            modality=payload.get("modality"),
            title=payload.get("title"),
            score=payload.get("score"),
            url=payload.get("url"),
            metadata=_sanitize_mapping(payload.get("metadata") or {}),
        )


@dataclass
class QueryTrace:
    query_id: str
    question: str
    created_at: str = field(default_factory=_now_iso)
    modalities_used: List[str] = field(default_factory=list)
    retrieved_chunks: List[ChunkRef] = field(default_factory=list)
    chosen_chunks: List[ChunkRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "question": self.question,
            "created_at": self.created_at,
            "modalities_used": list(self.modalities_used),
            "retrieved_chunks": [chunk.to_dict() for chunk in self.retrieved_chunks],
            "chosen_chunks": [chunk.to_dict() for chunk in self.chosen_chunks],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "QueryTrace":
        return cls(
            query_id=payload["query_id"],
            question=payload["question"],
            created_at=payload.get("created_at") or _now_iso(),
            modalities_used=list(payload.get("modalities_used", [])),
            retrieved_chunks=[ChunkRef.from_dict(ref) for ref in payload.get("retrieved_chunks", [])],
            chosen_chunks=[ChunkRef.from_dict(ref) for ref in payload.get("chosen_chunks", [])],
        )


class QueryTraceStore:
    """
    Lightweight append-only store for query traces captured during /cerebros runs.
    """

    def __init__(self, path: str | Path = DEFAULT_TRACE_STORE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, trace: QueryTrace) -> None:
        payload = _json_clone(trace.to_dict())
        line = json.dumps(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def get(self, query_id: str) -> Optional[QueryTrace]:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("query_id") == query_id:
                    return QueryTrace.from_dict(payload)
        return None

    def list_recent(self, limit: int = 10) -> List[QueryTrace]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entries = []
        for raw in reversed(lines):
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            entries.append(QueryTrace.from_dict(payload))
            if len(entries) >= limit:
                break
        return list(reversed(entries))

