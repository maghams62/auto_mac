from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .embedding_provider import EmbeddingProvider
from .vector_event import VectorEvent

logger = logging.getLogger(__name__)


class LocalVectorStore:
    """Simple JSON-backed vector store for synthetic data experiments."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._records = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                logger.warning("[LOCAL VECTOR STORE] Corrupt index at %s, reinitializing", self.path)
                self._records = []

    def upsert(self, events: Iterable[VectorEvent]) -> None:
        index = {record["event_id"]: record for record in self._records}
        inserted = 0
        for event in events:
            record = event.to_record()
            if not record.get("embedding"):
                raise ValueError(f"Event {event.event_id} missing embedding payload")
            index[event.event_id] = record
            inserted += 1

        self._records = list(index.values())
        self.path.write_text(json.dumps(self._records, indent=2))
        logger.info("[LOCAL VECTOR STORE] Upserted %s events (total=%s)", inserted, len(self._records))

    def search(
        self,
        query: str,
        *,
        embedding_provider: EmbeddingProvider,
        top_k: int = 5,
        filters: Optional[Dict[str, Iterable[str]]] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        if not self._records:
            return []

        embedding = embedding_provider.embed(query)
        if not embedding:
            return []

        filters = filters or {}
        results: List[Dict] = []
        for record in self._records:
            if since and datetime.fromisoformat(record["timestamp"]) < since:
                continue
            if not self._passes_filters(record, filters):
                continue
            similarity = self._cosine_similarity(record["embedding"], embedding)
            results.append({"score": similarity, "record": record})

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def _passes_filters(record: Dict, filters: Dict[str, Iterable[str]]) -> bool:
        for key, expected_values in filters.items():
            if not expected_values:
                continue
            record_values = set(record.get(key) or [])
            if not record_values.intersection(set(expected_values)):
                return False
        return True

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        length = min(len(vec_a), len(vec_b))
        dot = sum(vec_a[idx] * vec_b[idx] for idx in range(length))
        norm_a = math.sqrt(sum(v * v for v in vec_a[:length]))
        norm_b = math.sqrt(sum(v * v for v in vec_b[:length]))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

