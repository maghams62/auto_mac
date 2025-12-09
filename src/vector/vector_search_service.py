"""
Vector search service abstraction with Qdrant implementation.

Provides a backend-agnostic interface for indexing and querying ContextChunk
records stored in a VectorDB. Initial implementation uses Qdrant via HTTP API.
"""

from __future__ import annotations

import json
import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

import httpx

from ..config.qdrant import get_qdrant_collection_name
from .context_chunk import ContextChunk

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchOptions:
    """
    Options for semantic search queries.

    Attributes:
        top_k: Maximum number of chunks to return
        min_score: Minimum similarity score to keep a result
        source_types: Source types to include (doc, issue, slack, pr, etc.)
        components: Component filters
        services: Service filters
        tags: Tag filters (matches any tag)
        since: Only return chunks newer than this timestamp
    """

    top_k: int = 10
    min_score: float = 0.0
    source_types: Optional[List[str]] = None
    components: Optional[List[str]] = None
    services: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    since: Optional[datetime] = None
    metadata_filters: Dict[str, Any] = field(default_factory=dict)


class VectorSearchService(ABC):
    """Abstract interface for vector search implementations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        vectordb_config = config.get("vectordb", {})
        openai_config = config.get("openai", {})

        self.embedding_model = vectordb_config.get(
            "embedding_model",
            openai_config.get("embedding_model", "text-embedding-3-small"),
        )
        self._openai_client = None

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the backend has the required configuration."""

    @abstractmethod
    def index_chunks(self, chunks: List[ContextChunk]) -> bool:
        """Index chunks into the backend."""

    @abstractmethod
    def semantic_search(
        self,
        query: str,
        options: Optional[VectorSearchOptions] = None
    ) -> List[ContextChunk]:
        """Run a semantic search query."""

    # Shared helpers -----------------------------------------------------

    def _get_openai_client(self):
        """Lazy-load pooled OpenAI client."""
        if self._openai_client is None:
            from ..utils.openai_client import PooledOpenAIClient

            self._openai_client = PooledOpenAIClient.get_client(self.config)
        return self._openai_client

    def _embed_text(self, text: str) -> Optional[List[float]]:
        """Generate normalized embedding vector for text."""
        text = (text or "").strip()
        if not text:
            logger.debug("[VECTOR SEARCH] Skipping embedding generation for empty text payload")
            return None

        client = self._get_openai_client()
        try:
            response = client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000],  # Guardrail for extremely long docs
            )
            embedding = response.data[0].embedding

            # Normalize vector for cosine similarity
            norm = math.sqrt(sum(v * v for v in embedding))
            if norm > 0:
                embedding = [v / norm for v in embedding]

            return embedding
        except Exception as exc:
            logger.error(f"[VECTOR SEARCH] Failed to generate embedding: {exc}")
            return None


class QdrantVectorSearchService(VectorSearchService):
    """Qdrant-backed vector search implementation using HTTP API."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        vectordb_config = config.get("vectordb", {})

        self.enabled = vectordb_config.get("enabled", True)
        self.base_url = (vectordb_config.get("url") or "").rstrip("/")
        self.api_key = (vectordb_config.get("api_key") or "").strip() or None
        self.collection = get_qdrant_collection_name(vectordb_config.get("collection"))
        self.timeout = vectordb_config.get("timeout_seconds", 6.0)
        self.default_top_k = vectordb_config.get("default_top_k", 12)
        self.default_min_score = vectordb_config.get("min_score", 0.35)
        self.dimension = vectordb_config.get("dimension", 1536)

        self._http_client: Optional[httpx.Client] = None
        self._collection_ready = False

        if self.is_configured():
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["api-key"] = self.api_key

            self._http_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
            self._ensure_collection()

    def __del__(self):
        if self._http_client:
            try:
                self._http_client.close()
            except Exception:
                pass

    def is_configured(self) -> bool:
        return bool(
            self.enabled
            and self.base_url
            and self.collection
            and self.embedding_model
        )

    def index_chunks(self, chunks: List[ContextChunk]) -> bool:
        if not self.is_configured() or not chunks or not self._http_client:
            return False

        if not self._collection_ready:
            try:
                self._ensure_collection()
            except RuntimeError as exc:
                logger.error("[VECTOR SEARCH] %s", exc)
                return False

        points = []
        total_chars = 0
        truncated_chars = 0
        embedding_failures = 0
        for chunk in chunks:
            raw_text = chunk.text or ""
            total_chars += len(raw_text)
            safe_text = ContextChunk.clamp_text(raw_text)
            if len(raw_text) > len(safe_text):
                truncated_chars += len(raw_text) - len(safe_text)

            embedding = self._embed_text(chunk.text)
            if not embedding:
                embedding_failures += 1
                logger.debug(
                    "[VECTOR SEARCH] Skipping chunk %s (%s) due to missing embedding",
                    chunk.chunk_id,
                    chunk.entity_id,
                )
                continue
            point_id = self._normalize_point_id(chunk)
            points.append(
                {
                    "id": point_id,
                    "vector": embedding,
                    "payload": self._chunk_to_payload(chunk, text_override=safe_text),
                }
            )

        if not points:
            logger.warning(
                "[VECTOR SEARCH] No points to index (embeddings missing=%s/%s)",
                embedding_failures,
                len(chunks),
            )
            return False

        payload = {"points": points}
        payload_bytes = len(json.dumps(payload).encode("utf-8"))

        try:
            start = time.perf_counter()
            response = self._http_client.put(
                f"/collections/{self.collection}/points?wait=true",
                json=payload,
            )
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "[VECTOR SEARCH] Indexed %s chunks into collection '%s' "
                "(skipped=%s truncated_chars=%s payload_kb=%.1f status=%s latency_ms=%.1f)",
                len(points),
                self.collection,
                len(chunks) - len(points),
                truncated_chars,
                payload_bytes / 1024.0,
                response.status_code,
                latency_ms,
            )
            return True
        except httpx.HTTPStatusError as exc:
            sample_point = points[0] if points else {}
            logger.error(
                "[VECTOR SEARCH] Qdrant upsert failed (status=%s collection=%s payload_kb=%.1f). "
                "Sample point id=%s vector_dim=%s error=%s",
                exc.response.status_code,
                self.collection,
                payload_bytes / 1024.0,
                sample_point.get("id"),
                len(sample_point.get("vector") or []),
                exc.response.text,
            )
            return False
        except Exception as exc:
            logger.error(f"[VECTOR SEARCH] Failed to index chunks: {exc}")
            return False

    def semantic_search(
        self,
        query: str,
        options: Optional[VectorSearchOptions] = None
    ) -> List[ContextChunk]:
        if not self.is_configured() or not self._http_client:
            return []

        if not self._collection_ready:
            try:
                self._ensure_collection()
            except RuntimeError as exc:
                logger.error("[VECTOR SEARCH] %s", exc)
                return []

        query = (query or "").strip()
        if not query:
            logger.debug("[VECTOR SEARCH] Empty query string received; returning no results")
            return []

        embedding = self._embed_text(query)
        if not embedding:
            logger.debug("[VECTOR SEARCH] Failed to generate embedding for query '%s'", query)
            return []

        options = options or VectorSearchOptions()
        limit = options.top_k or self.default_top_k
        min_score = options.min_score or self.default_min_score

        payload: Dict[str, Any] = {
            "vector": embedding,
            "limit": limit,
            "with_payload": True,
        }

        filter_clause = self._build_filter(options)
        if filter_clause:
            payload["filter"] = filter_clause

        logger.debug(
            "[VECTOR SEARCH] Executing query '%s' (limit=%s, min_score=%.2f) with filters=%s",
            query,
            limit,
            min_score,
            filter_clause,
        )

        try:
            response = self._http_client.post(
                f"/collections/{self.collection}/points/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error(f"[VECTOR SEARCH] Search request failed: {exc}")
            return []

        results = []
        for point in data.get("result", []):
            score = point.get("score", 0.0)
            if score < min_score:
                continue

            payload = point.get("payload") or {}
            chunk = self._payload_to_chunk(payload, point.get("id"))
            chunk.metadata.setdefault("_score", score)
            results.append(chunk)

        logger.info(
            "[VECTOR SEARCH] Retrieved %s chunks for query '%s' (limit=%s)",
            len(results),
            query,
            limit,
        )
        return results

    # Internal helpers ---------------------------------------------------

    def _ensure_collection(self):
        if not self._http_client or self._collection_ready:
            return

        try:
            response = self._http_client.get(f"/collections/{self.collection}")
            if response.status_code == 200:
                self._collection_ready = True
                return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise RuntimeError(
                    f"Failed to inspect Qdrant collection '{self.collection}': {exc}"
                ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to inspect Qdrant collection '{self.collection}': {exc}"
            ) from exc

        logger.info(f"[VECTOR SEARCH] Creating Qdrant collection '{self.collection}'")
        try:
            create_payload = {
                "vectors": {
                    "size": self.dimension,
                    "distance": "Cosine",
                }
            }
            response = self._http_client.put(
                f"/collections/{self.collection}",
                json=create_payload,
            )
            response.raise_for_status()
            self._collection_ready = True
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Qdrant collection '{self.collection}': {exc}"
            ) from exc

    @staticmethod
    def _chunk_to_payload(
        chunk: ContextChunk,
        text_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_text = text_override if text_override is not None else ContextChunk.clamp_text(chunk.text)
        payload: Dict[str, Any] = {
            "chunk_id": chunk.chunk_id,
            "entity_id": chunk.entity_id,
            "source_type": chunk.source_type,
            "text": safe_text,
            "component": chunk.component,
            "service": chunk.service,
            "tags": chunk.tags,
            "metadata": chunk.metadata or {},
            "collection": chunk.collection or None,
        }

        if chunk.timestamp:
            timestamp = chunk.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)
            payload["timestamp"] = timestamp.timestamp()
            payload["timestamp_iso"] = timestamp.isoformat()

        return payload

    def _payload_to_chunk(self, payload: Dict[str, Any], point_id: Any) -> ContextChunk:
        timestamp = None
        if "timestamp" in payload:
            try:
                timestamp = datetime.fromtimestamp(payload["timestamp"], tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                timestamp = None
        elif payload.get("timestamp_iso"):
            try:
                timestamp = datetime.fromisoformat(payload["timestamp_iso"])
            except (TypeError, ValueError):
                timestamp = None

        return ContextChunk(
            chunk_id=str(payload.get("chunk_id") or point_id or ContextChunk.generate_chunk_id()),
            entity_id=payload.get("entity_id", "unknown"),
            source_type=payload.get("source_type", "doc"),
            text=payload.get("text", ""),
            component=payload.get("component"),
            service=payload.get("service"),
            timestamp=timestamp,
            tags=payload.get("tags", []),
            metadata=payload.get("metadata") or {},
            collection=payload.get("collection") or self.collection,
        )

    @staticmethod
    def _build_filter(options: VectorSearchOptions) -> Optional[Dict[str, Any]]:
        must_clauses: List[Dict[str, Any]] = []

        def add_match(key: str, values: Optional[List[str]]):
            if values:
                must_clauses.append({"key": key, "match": {"any": values}})

        add_match("source_type", options.source_types)
        add_match("component", options.components)
        add_match("service", options.services)
        add_match("tags", options.tags)

        if options.since:
            since = options.since
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            else:
                since = since.astimezone(timezone.utc)
            must_clauses.append(
                {
                    "key": "timestamp",
                    "range": {"gte": since.timestamp()},
                }
            )

        for key, value in options.metadata_filters.items():
            if isinstance(value, list):
                must_clauses.append({"key": f"metadata.{key}", "match": {"any": value}})
            else:
                must_clauses.append({"key": f"metadata.{key}", "match": {"value": value}})

        if not must_clauses:
            return None

        return {"must": must_clauses}

    def _normalize_point_id(self, chunk: ContextChunk) -> str:
        candidate = chunk.entity_id or chunk.chunk_id
        if candidate:
            candidate_str = str(candidate)
            try:
                UUID(candidate_str)
                return candidate_str
            except ValueError:
                pass
            return str(uuid5(NAMESPACE_URL, candidate_str))
        return str(uuid4())
