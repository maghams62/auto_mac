from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import httpx

from .embedding_provider import EmbeddingProvider
from .vector_event import VectorEvent

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Qdrant-backed vector store with the same interface as LocalVectorStore."""

    def __init__(
        self,
        *,
        base_url: str,
        collection: str,
        api_key: Optional[str] = None,
        dimension: int = 1536,
        timeout: float = 10.0,
    ):
        if not base_url:
            raise ValueError("Qdrant base URL must be provided via config/env.")

        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.dimension = dimension

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["api-key"] = api_key

        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout)
        self._ensure_collection()

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - best effort
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def upsert(self, events: Iterable[VectorEvent]) -> None:
        points = []
        for event in events:
            record = event.to_record()
            embedding = record.get("embedding")
            if not embedding:
                raise ValueError(f"[QDRANT VECTOR STORE] Event {event.event_id} missing embedding payload")

            payload = dict(record)
            payload["timestamp_epoch"] = self._timestamp_epoch(record.get("timestamp"))
            points.append(
                {
                    "id": self._point_id(record["event_id"]),
                    "vector": embedding,
                    "payload": payload,
                }
            )

        if not points:
            logger.warning("[QDRANT VECTOR STORE] No points to upsert.")
            return

        self._put(
            f"/collections/{self.collection}/points?wait=true",
            json={"points": points},
            log_context=f"upsert {len(points)} events",
        )

    def search(
        self,
        query: str,
        *,
        embedding_provider: EmbeddingProvider,
        top_k: int = 5,
        filters: Optional[Dict[str, Iterable[str]]] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        embedding = embedding_provider.embed(query)
        if not embedding:
            return []

        filter_clause = self._build_filter(filters or {}, since)

        payload: Dict[str, object] = {
            "vector": embedding,
            "limit": top_k,
            "with_payload": True,
        }
        if filter_clause:
            payload["filter"] = filter_clause

        response = self._client.post(
            f"/collections/{self.collection}/points/search",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("result", []):
            score = item.get("score")
            payload = item.get("payload") or {}
            results.append({"score": score, "record": payload})
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_collection(self) -> None:
        try:
            response = self._client.get(f"/collections/{self.collection}")
            if response.status_code == 200:
                return
            if response.status_code != 404:
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to inspect Qdrant collection '{self.collection}': {exc}") from exc

        logger.info("[QDRANT VECTOR STORE] Creating collection '%s'", self.collection)
        payload = {
            "vectors": {
                "size": self.dimension,
                "distance": "Cosine",
            }
        }
        self._put(f"/collections/{self.collection}", json=payload, log_context="create collection")

    def _put(self, path: str, *, json: Dict[str, object], log_context: str) -> None:
        response = self._client.put(path, json=json)
        try:
            response.raise_for_status()
            logger.info("[QDRANT VECTOR STORE] Successful %s (status=%s)", log_context, response.status_code)
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors
            details = exc.response.text
            raise RuntimeError(f"Qdrant request failed during {log_context}: {details}") from exc

    @staticmethod
    def _point_id(event_id: str) -> str:
        """Convert arbitrary event identifiers to UUID strings accepted by Qdrant."""
        if not event_id:
            return str(uuid.uuid4())
        return str(uuid.uuid5(uuid.NAMESPACE_URL, event_id))

    @staticmethod
    def _timestamp_epoch(timestamp_str: Optional[str]) -> float:
        if not timestamp_str:
            return 0.0
        try:
            return datetime.fromisoformat(timestamp_str).timestamp()
        except ValueError:
            return 0.0

    @staticmethod
    def _build_filter(filters: Dict[str, Iterable[str]], since: Optional[datetime]) -> Optional[Dict]:
        must: List[Dict] = []

        for field, values in filters.items():
            values = list(values or [])
            if not values:
                continue
            should = [{"key": field, "match": {"value": value}} for value in values]
            if should:
                must.append({"should": should})

        if since:
            must.append(
                {
                    "key": "timestamp_epoch",
                    "range": {"gte": since.timestamp()},
                }
            )

        return {"must": must} if must else None

